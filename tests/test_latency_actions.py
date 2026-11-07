import subprocess
import threading
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import latency
import server


def test_sequence_order_and_single_outer_timing():
    with patch.object(server, 'shell', return_value='') as command:
        result = server.run_actions([
            {'action': 'key', 'key': 'down', 'repeat': 5},
            {'action': 'text', 'text': 'a movie'},
            {'action': 'key', 'key': 'enter'},
        ])
    assert result['ok'] and result['completed_steps'] == 3
    assert [call.args for call in command.call_args_list] == [
        ('input', 'keyevent', '20', '20', '20', '20', '20'),
        ('input', 'text', 'a%smovie'),
        ('input', 'keyevent', 'KEYCODE_ENTER'),
    ]
    assert latency.recent_timings(1)[0]['tool'] == 'run_actions'
    assert latency.current.get() is None


@pytest.mark.parametrize('bad_step', [
    {'action': 'text', 'text': '\u2603'},
    {'action': 'key', 'key': 'reboot;rm'},
    {'action': 'key', 'key': 'up', 'repeat': True},
    {'action': 'wait', 'seconds': float('nan')},
    {'action': 'wait', 'seconds': -1},
    {'action': 'open_app', 'app': 'unknown'},
    {'action': 'key', 'key': 'up', 'command': 'reboot'},
])
def test_entire_batch_is_validated_before_first_action(bad_step):
    with patch.object(server, 'shell') as command:
        with pytest.raises(ValidationError):
            server.run_actions([{'action': 'key', 'key': 'home'}, bad_step])
        command.assert_not_called()


@pytest.mark.parametrize('steps', [
    [], [{'action': 'key', 'key': 'up'}] * 21,
    [{'action': 'key', 'key': 'up', 'repeat': 30}] * 5,
    [{'action': 'wait', 'seconds': 5}] * 3,
])
def test_batch_limits_before_execution(steps):
    with patch.object(server, 'shell') as command, patch.object(server.time, 'sleep') as sleep:
        with pytest.raises(ValueError):
            server.run_actions(steps)
        command.assert_not_called()
        sleep.assert_not_called()


def test_failure_stops_without_replaying_previous_actions():
    with patch.object(server, 'shell', side_effect=['', RuntimeError('offline')]) as command:
        result = server.run_actions([
            {'action': 'key', 'key': 'home'},
            {'action': 'key', 'key': 'down'},
            {'action': 'key', 'key': 'ok'},
        ])
    assert not result['ok']
    assert result['completed_steps'] == 1 and result['failed_step'] == 2
    assert command.call_count == 2
    assert latency.recent_timings(1)[0]['ok'] is False


def test_wait_and_launch_in_sequence():
    with patch.object(server, 'shell', side_effect=[
        'com.google.android.youtube.tv/.Main', 'Status: ok', '',
    ]) as command, patch.object(server.time, 'sleep') as sleep:
        result = server.run_actions([
            {'action': 'open_app', 'app': 'youtube'},
            {'action': 'wait', 'seconds': 0.5},
            {'action': 'key', 'key': 'search'},
        ])
    assert result['ok']
    sleep.assert_called_once_with(0.5)
    assert command.call_count == 3


def test_adb_honors_remaining_batch_budget_and_records_failure():
    timing = latency.RequestTiming(deadline=server.time.perf_counter() + 2)
    token = latency.current.set(timing)
    try:
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('adb', 2)) as run:
            with pytest.raises(subprocess.TimeoutExpired):
                server.adb('devices')
        assert 0 < run.call_args.kwargs['timeout'] <= 2
        assert timing.adb_calls == 1
        timing.deadline = server.time.perf_counter() - 1
        with patch.object(subprocess, 'run') as run:
            with pytest.raises(TimeoutError):
                server.adb('devices')
            run.assert_not_called()
    finally:
        latency.current.reset(token)


def test_timings_include_adb_without_logging_typed_text(capsys):
    with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')):
        server.type_text('private search query')
    timing = latency.recent_timings(1)[0]
    assert timing['tool'] == 'type_text' and timing['adb_calls'] == 1
    assert timing['total_ms'] >= timing['adb_ms'] >= 0
    captured = capsys.readouterr()
    assert not captured.out
    assert 'private search query' not in captured.err


def test_status_is_compact_with_explicit_detail_escape_hatch():
    output = 'noise\n' * 1000 + '  mResumedActivity: ActivityRecord{abc app/.Main}\n'
    with patch.object(server, 'shell', return_value=output):
        assert server.get_tv_status() == 'mResumedActivity: ActivityRecord{abc app/.Main}'
        assert server.get_tv_status(detail=True) == output


def test_measurement_is_read_only():
    with patch.object(server, 'shell', return_value='tv-latency-check') as command:
        result = server.measure_tv_latency(samples=3)
    assert len(result['samples_ms']) == 3
    assert all(call.args == ('echo', 'tv-latency-check') for call in command.call_args_list)


def test_sequence_does_not_interleave_with_another_remote_request():
    started = threading.Event()
    release = threading.Event()
    competitor_started = threading.Event()
    sent = []

    def fake_shell(*args):
        sent.append(args[-1])
        if args[-1] == '20':
            started.set()
            assert release.wait(3)
        return ''

    def competing_request():
        competitor_started.set()
        server.press_key('home')

    with patch.object(server, 'shell', side_effect=fake_shell):
        first = threading.Thread(target=server.run_actions, args=([
            {'action': 'key', 'key': 'down'}, {'action': 'key', 'key': 'ok'},
        ],))
        second = threading.Thread(target=competing_request)
        first.start()
        try:
            assert started.wait(3)
            second.start()
            assert competitor_started.wait(3)
        finally:
            release.set()
            first.join(3)
            if second.ident is not None:
                second.join(3)
        assert not first.is_alive() and not second.is_alive()
    assert sent == ['20', '23', '3']
