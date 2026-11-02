import os
import re
import subprocess
import time
import threading
from typing import Annotated, Literal, overload
from pydantic import Field
from mcp.server.fastmcp import FastMCP, Image

APPS = {'youtube': 'com.google.android.youtube.tv', 'netflix': 'com.netflix.ninja', 'prime_video': 'com.amazon.amazonvideo.livingroom', 'jiohotstar': 'in.startv.hotstar'}
KEYS = {'home': 3, 'back': 4, 'up': 19, 'down': 20, 'left': 21, 'right': 22, 'ok': 23, 'volume_up': 24, 'volume_down': 25, 'mute': 164, 'play_pause': 85}
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
def press_key(key: Literal['home', 'back', 'up', 'down', 'left', 'right', 'ok', 'volume_up', 'volume_down', 'mute', 'play_pause']) -> str:
    """Press one remote key on the configured TV."""
    shell('input', 'keyevent', str(KEYS[key]))
    return 'Sent ' + key

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
