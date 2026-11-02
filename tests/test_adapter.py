from unittest.mock import patch
import subprocess
import pytest
import server


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
