import os
import re
import subprocess
import time
import threading
import shlex
from typing import Annotated, Literal, cast, overload
from pydantic import Field
from mcp.server.fastmcp import FastMCP, Image

APPS = {'youtube': 'com.google.android.youtube.tv', 'netflix': 'com.netflix.ninja', 'prime_video': 'com.amazon.amazonvideo.livingroom', 'jiohotstar': 'in.startv.hotstar'}
# Android KeyEvent names avoid device-specific numeric magic for extra controls.
KEYS = {
    'home': '3', 'back': '4', 'up': '19', 'down': '20', 'left': '21',
    'right': '22', 'ok': '23', 'volume_up': '24', 'volume_down': '25',
    'mute': '164', 'play_pause': '85',
}
KEYS.update({name: 'KEYCODE_' + code for name, code in {
    'power': 'POWER', 'sleep': 'SLEEP', 'wake': 'WAKEUP',
    'menu': 'MENU', 'settings': 'SETTINGS', 'search': 'SEARCH',
    'assistant': 'VOICE_ASSIST', 'apps': 'ALL_APPS', 'recent_apps': 'APP_SWITCH',
    'play': 'MEDIA_PLAY', 'pause': 'MEDIA_PAUSE', 'stop': 'MEDIA_STOP',
    'rewind': 'MEDIA_REWIND', 'fast_forward': 'MEDIA_FAST_FORWARD',
    'next': 'MEDIA_NEXT', 'previous': 'MEDIA_PREVIOUS', 'record': 'MEDIA_RECORD',
    'skip_forward': 'MEDIA_SKIP_FORWARD', 'skip_backward': 'MEDIA_SKIP_BACKWARD',
    'channel_up': 'CHANNEL_UP', 'channel_down': 'CHANNEL_DOWN',
    'last_channel': 'LAST_CHANNEL', 'guide': 'GUIDE', 'info': 'INFO',
    'tv': 'TV', 'input': 'TV_INPUT', 'captions': 'CAPTIONS',
    'audio_track': 'MEDIA_AUDIO_TRACK', 'teletext': 'TV_TELETEXT',
    'red': 'PROG_RED', 'green': 'PROG_GREEN', 'yellow': 'PROG_YELLOW',
    'blue': 'PROG_BLUE', 'picture_in_picture': 'WINDOW', 'zoom_in': 'ZOOM_IN',
    'zoom_out': 'ZOOM_OUT', 'enter': 'ENTER', 'delete': 'DEL',
    'forward_delete': 'FORWARD_DEL', 'escape': 'ESCAPE', 'tab': 'TAB',
    'space': 'SPACE', 'page_up': 'PAGE_UP', 'page_down': 'PAGE_DOWN',
    'dash': 'MINUS', 'period': 'PERIOD', 'help': 'HELP',
    'hdmi_1': 'TV_INPUT_HDMI_1', 'hdmi_2': 'TV_INPUT_HDMI_2',
    'hdmi_3': 'TV_INPUT_HDMI_3', 'hdmi_4': 'TV_INPUT_HDMI_4',
    'composite_1': 'TV_INPUT_COMPOSITE_1', 'composite_2': 'TV_INPUT_COMPOSITE_2',
    'component_1': 'TV_INPUT_COMPONENT_1', 'component_2': 'TV_INPUT_COMPONENT_2',
    'vga': 'TV_INPUT_VGA_1', 'antenna': 'TV_ANTENNA_CABLE',
}.items()})
KEYS.update({str(n): 'KEYCODE_' + str(n) for n in range(10)})
RemoteKey = Literal[
    'home', 'back', 'up', 'down', 'left', 'right',
    'ok', 'volume_up', 'volume_down', 'mute', 'play_pause', 'power',
    'sleep', 'wake', 'menu', 'settings', 'search', 'assistant',
    'apps', 'recent_apps', 'play', 'pause', 'stop', 'rewind',
    'fast_forward', 'next', 'previous', 'record', 'skip_forward', 'skip_backward',
    'channel_up', 'channel_down', 'last_channel', 'guide', 'info', 'tv',
    'input', 'captions', 'audio_track', 'teletext', 'red', 'green',
    'yellow', 'blue', 'picture_in_picture', 'zoom_in', 'zoom_out', 'enter',
    'delete', 'forward_delete', 'escape', 'tab', 'space', 'page_up',
    'page_down', 'dash', 'period', 'help', 'hdmi_1', 'hdmi_2',
    'hdmi_3', 'hdmi_4', 'composite_1', 'composite_2', 'component_1', 'component_2',
    'vga', 'antenna', '0', '1', '2', '3',
    '4', '5', '6', '7', '8', '9',
]

endpoint = os.getenv('TV_ENDPOINT', '192.168.68.51:5555')
if not re.fullmatch(r'[a-zA-Z0-9.-]+:[0-9]{1,5}', endpoint):
    raise ValueError('TV_ENDPOINT must be hostname:port')
mcp = FastMCP('Mi TV Adapter', host='0.0.0.0', port=8000)

@overload
def adb(*args: str, binary: Literal[False] = False) -> str: ...

@overload
def adb(*args: str, binary: Literal[True]) -> bytes: ...

@overload
def adb(*args: str, binary: bool) -> str | bytes: ...

def adb(*args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run([os.getenv('ADB_BINARY', 'adb'), *args], capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip() or 'ADB failed')
    return result.stdout if binary else result.stdout.decode(errors='replace').strip()

def shell(*args: str) -> str:
    return adb('-s', endpoint, 'shell', *args)

@mcp.tool()
def connect_tv() -> str:
    """Connect to the configured TV. User must enable debugging and authorize this computer on TV."""
    return adb('connect', endpoint)

@mcp.tool()
def get_tv_status() -> str:
    """Read the TV foreground activity and connection status."""
    return shell('dumpsys', 'activity', 'activities')[-24000:]

@mcp.tool()
def list_apps() -> dict:
    """List supported app aliases and package identifiers."""
    return APPS

@mcp.tool()
def open_app(app: Literal['youtube', 'netflix', 'prime_video', 'jiohotstar']) -> str:
    """Launch a supported TV application and return observed activity state."""
    package = APPS[app]
    activities = shell('cmd', 'package', 'resolve-activity', '--brief', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LEANBACK_LAUNCHER', package).splitlines()
    component = activities[-1].strip() if activities else ''
    if not re.fullmatch(re.escape(package) + r'/[\w.$]+', component):
        raise RuntimeError('No valid launch activity found for app')
    launched = shell('am', 'start', '-W', '-n', component)
    if 'Error' in launched:
        raise RuntimeError(launched)
    return launched

@mcp.tool()
def list_remote_controls() -> dict:
    """List available remote buttons and device-dependent limitations."""
    return {
        'keys': list(KEYS),
        'limits': [
            'Key delivery does not guarantee the TV or foreground app handles it.',
            'Wake requires reachable ADB; full shutdown cannot be reversed by this adapter.',
            'Assistant opens the TV assistant only; laptop microphone audio is not forwarded.',
            'Inputs, tuner channels, captions, recording and picture-in-picture depend on TV/app support.',
        ],
    }


@mcp.tool()
def press_key(
    key: RemoteKey,
    long_press: bool = False,
    repeat: Annotated[int, Field(ge=1, le=30)] = 1,
) -> str:
    """Send a remote button, optionally as an Android long press or 1–30 presses.
    Power toggles standby; prefer set_power for explicit sleep/wake.
    Success means sent, not that the TV supports the button.
    """
    name = key
    if name not in KEYS:
        raise ValueError('Unknown remote key; call list_remote_controls')
    if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 30:
        raise ValueError('repeat must be an integer from 1 to 30')
    if not isinstance(long_press, bool):
        raise ValueError('long_press must be a boolean')
    args = ['input', 'keyevent']
    if long_press:
        args.append('--longpress')
    shell(*args, *([KEYS[name]] * repeat))
    return f'Sent {name} ({repeat} press(es)' + (', long press)' if long_press else ')')


@mcp.tool()
def set_power(state: Literal['on', 'off']) -> str:
    """Wake or sleep the TV without toggling. Wake only works while ADB is reachable."""
    if state not in ('on', 'off'):
        raise ValueError('state must be on or off')
    return press_key('wake' if state == 'on' else 'sleep')


@mcp.tool()
def select_input(source: Literal[
    'input', 'tv', 'antenna', 'hdmi_1', 'hdmi_2', 'hdmi_3', 'hdmi_4',
    'composite_1', 'composite_2', 'component_1', 'component_2', 'vga',
]) -> str:
    """Open the input picker (input) or request a named input. TV support varies."""
    allowed = {'input', 'tv', 'antenna', 'hdmi_1', 'hdmi_2', 'hdmi_3', 'hdmi_4',
               'composite_1', 'composite_2', 'component_1', 'component_2', 'vga'}
    if source not in allowed:
        raise ValueError('Unsupported input source')
    return press_key(cast(RemoteKey, source))


@mcp.tool()
def enter_channel(channel: str, confirm: bool = True) -> str:
    """Enter 1–6 channel digits, optionally with a subchannel dash/dot, then Enter.
    Open live TV/tuner first. Does not tune an external set-top box without TV support.
    """
    if not re.fullmatch(r'[0-9]{1,6}(?:[-.][0-9]{1,3})?', channel):
        raise ValueError('Use 1–6 channel digits and an optional 1–3 digit subchannel')
    codes = [KEYS[{'-': 'dash', '.': 'period'}.get(char, char)] for char in channel]
    if confirm:
        codes.append(KEYS['enter'])
    shell('input', 'keyevent', *codes)
    return 'Sent channel ' + channel


@mcp.tool()
def type_text(text: Annotated[str, Field(min_length=1, max_length=500)]) -> str:
    """Type printable ASCII into the focused TV text field. Focus it first.
    Unicode and the literal sequence %s are unsupported by Android input text.
    Use press_key(enter) to submit. This does not open app-specific search.
    """
    if not 1 <= len(text) <= 500 or any(not 32 <= ord(c) <= 126 for c in text) or '%s' in text:
        raise ValueError('Use 1–500 printable ASCII characters, without the literal sequence %s')
    # adb shell joins arguments for the remote shell; quote for that shell, not Windows.
    shell('input', 'text', shlex.quote(text.replace(' ', '%s')))
    return f'Sent {len(text)} characters'


volume_lock = threading.Lock()

@mcp.tool()
def hold_volume(
    direction: Literal['up', 'down'],
    seconds: Annotated[float, Field(ge=0.2, le=10)] = 2.0,
) -> dict:
    """Continuously raise or lower volume for 0.2–10 seconds, like holding a volume button.
    Use this for rapid volume changes instead of repeated press_key calls.
    This sends repeated volume events; it stops automatically after the requested duration.
    """
    if direction not in ('up', 'down') or not 0.2 <= seconds <= 10:
        raise ValueError('Use direction up/down and a duration from 0.2 to 10 seconds')
    if not volume_lock.acquire(blocking=False):
        raise RuntimeError('A volume adjustment is already running')
    try:
        start = time.monotonic()
        deadline = start + seconds
        count = 0
        keycode = '24' if direction == 'up' else '25'
        while time.monotonic() < deadline:
            shell('input', 'keyevent', keycode)
            count += 1
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.08, remaining))
        return {'direction': direction, 'events_sent': count,
                'elapsed_seconds': round(time.monotonic() - start, 2)}
    finally:
        volume_lock.release()

@mcp.tool()
def get_screenshot() -> Image:
    """Capture the TV screen. Protected streaming content and HDMI may refuse screenshots."""
    data = adb('-s', endpoint, 'exec-out', 'screencap', '-p', binary=True)
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('TV did not return a PNG; protected content may block capture')
    return Image(data=data, format='png')

if __name__ == '__main__':
    transport = os.getenv('MCP_TRANSPORT', 'stdio')
    if transport not in ('stdio', 'sse', 'streamable-http'):
        raise ValueError('MCP_TRANSPORT must be stdio, sse, or streamable-http')
    mcp.run(transport=transport)
