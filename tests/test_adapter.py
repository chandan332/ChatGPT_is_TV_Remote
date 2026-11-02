from unittest.mock import patch
import subprocess
import pytest
import server
import shlex
from typing import get_args


def test_resolved_activity_cannot_inject_shell():
    with patch.object(server, 'shell', return_value='com.google.android.youtube.tv/.Main;reboot') as call:
        with pytest.raises(RuntimeError):
            server.open_app('youtube')
        assert call.call_count == 1


def test_launch_failure_is_not_success():
    with patch.object(server, 'shell', side_effect=['com.google.android.youtube.tv/.Main', 'Error: blocked']):
        with pytest.raises(RuntimeError):
            server.open_app('youtube')


def test_protected_screenshot_rejected():
    with patch.object(server, 'adb', return_value=b''):
        with pytest.raises(RuntimeError):
            server.get_screenshot()


def test_adb_timeout_is_bounded():
    with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('adb',20)) as run:
        with pytest.raises(subprocess.TimeoutExpired):
            server.adb('devices')
        assert run.call_args.kwargs['timeout'] == 20

@pytest.mark.parametrize('direction,seconds', [('oops', 1), ('up', 0), ('down', 11), ('up', float('nan'))])
def test_hold_volume_rejects_invalid_requests(direction, seconds):
    with patch.object(server, 'shell') as command:
        with pytest.raises(ValueError):
            server.hold_volume(direction, seconds)
        command.assert_not_called()


def test_hold_volume_stops_and_uses_requested_direction():
    with patch.object(server.time, 'monotonic', side_effect=[0, 0, 0.1, 0.3, 0.3]), patch.object(server.time, 'sleep'), patch.object(server, 'shell') as command:
        result = server.hold_volume('down', 0.2)
        command.assert_called_once_with('input', 'keyevent', '25')
        assert result['events_sent'] == 1


def test_volume_lock_released_on_connection_error():
    with patch.object(server, 'shell', side_effect=RuntimeError('offline')):
        with pytest.raises(RuntimeError):
            server.hold_volume('up', 0.2)
    assert not server.volume_lock.locked()


def test_empty_activity_has_clear_error():
    with patch.object(server, 'shell', return_value=''):
        with pytest.raises(RuntimeError, match='No valid launch activity'):
            server.open_app('youtube')


def test_remote_schema_exposes_every_key():
    assert set(get_args(server.RemoteKey)) == set(server.KEYS)


def test_long_press_and_repeat():
    with patch.object(server, 'shell') as command:
        server.press_key('ok', long_press=True, repeat=3)
        command.assert_called_once_with('input', 'keyevent', '--longpress', '23', '23', '23')


@pytest.mark.parametrize('kwargs', [
    {'key': 'reboot;rm'}, {'key': 'up', 'repeat': 0},
    {'key': 'up', 'repeat': 31}, {'key': 'up', 'repeat': True},
    {'key': 'up', 'repeat': 1.5}, {'key': 'up', 'long_press': 'yes'},
])
def test_invalid_remote_requests_do_not_reach_tv(kwargs):
    with patch.object(server, 'shell') as command:
        with pytest.raises(ValueError):
            server.press_key(**kwargs)
        command.assert_not_called()


@pytest.mark.parametrize('state,code', [('on', 'KEYCODE_WAKEUP'), ('off', 'KEYCODE_SLEEP')])
def test_power_uses_explicit_state_not_toggle(state, code):
    with patch.object(server, 'shell') as command:
        server.set_power(state)
        command.assert_called_once_with('input', 'keyevent', code)


def test_channel_digits_preserve_leading_zero_and_subchannel():
    with patch.object(server, 'shell') as command:
        server.enter_channel('07-2')
        command.assert_called_once_with('input', 'keyevent', 'KEYCODE_0', 'KEYCODE_7',
                                        'KEYCODE_MINUS', 'KEYCODE_2', 'KEYCODE_ENTER')


@pytest.mark.parametrize('channel', ['', '1234567', '-1', '1;reboot', '1.2.3'])
def test_invalid_channel_rejected(channel):
    with patch.object(server, 'shell') as command:
        with pytest.raises(ValueError):
            server.enter_channel(channel)
        command.assert_not_called()


def test_input_selection():
    with patch.object(server, 'shell') as command:
        server.select_input('hdmi_2')
        command.assert_called_once_with('input', 'keyevent', 'KEYCODE_TV_INPUT_HDMI_2')
        with pytest.raises(ValueError):
            server.select_input('home')
        assert command.call_count == 1


@pytest.mark.parametrize('text', ["it's a movie", 'hello; reboot', '$(id) & `id`', '"quoted" \\ path'])
def test_text_is_one_quoted_remote_shell_argument(text):
    with patch.object(server, 'shell') as command:
        server.type_text(text)
        args = command.call_args.args
        assert args[:2] == ('input', 'text')
        assert shlex.split(args[2]) == [text.replace(' ', '%s')]


@pytest.mark.parametrize('text', ['', 'x' * 501, 'line\nbreak', '\u2603', '%s'])
def test_unsupported_text_rejected(text):
    with patch.object(server, 'shell') as command:
        with pytest.raises(ValueError):
            server.type_text(text)
        command.assert_not_called()
