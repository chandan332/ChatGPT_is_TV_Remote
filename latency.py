"""Bounded, argument-free tool timing; stderr leaves MCP stdio intact."""
import json
import os
import sys
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Callable, ParamSpec, TypeVar


@dataclass
class RequestTiming:
    adb_calls: int = 0
    adb_ms: float = 0
    deadline: float | None = None


current: ContextVar[RequestTiming | None] = ContextVar('request_timing', default=None)
history: deque[dict] = deque(maxlen=100)
history_lock = threading.Lock()
command_lock = threading.RLock()
P = ParamSpec('P')
R = TypeVar('R')


def timed(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        if current.get() is not None:
            return function(*args, **kwargs)
        started = time.perf_counter()
        received_at = time.time()
        timing = RequestTiming()
        token = current.set(timing)
        ok = False
        acquired = started
        try:
            # A sequence must not interleave with another remote command.
            with command_lock:
                acquired = time.perf_counter()
                result = function(*args, **kwargs)
                ok = not (isinstance(result, dict) and result.get('ok') is False)
                return result
        finally:
            record = {
                'request_id': uuid.uuid4().hex[:12], 'tool': function.__name__,
                'received_at_unix': round(received_at, 3), 'ok': ok,
                'total_ms': round((time.perf_counter() - started) * 1000, 2),
                'queue_ms': round((acquired - started) * 1000, 2),
                'adb_calls': timing.adb_calls, 'adb_ms': round(timing.adb_ms, 2),
            }
            current.reset(token)
            with history_lock:
                history.append(record)
            if os.getenv('TV_TIMING_LOG', '1') == '1':
                print(json.dumps({'event': 'tv_tool_timing', **record}), file=sys.stderr)
    return wrapped


def recent_timings(limit: int) -> list[dict]:
    with history_lock:
        return list(history)[-limit:]
