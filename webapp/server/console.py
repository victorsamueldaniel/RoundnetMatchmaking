"""Per-thread stdout capture.

The engine reports progress with print(). Several generations can run at the
same time in the server's thread pool, so stdout is replaced once by a proxy
that sends each thread's writes to its own sink.
"""

import sys
import threading

_local = threading.local()


class _ThreadRoutedStdout:
    def __init__(self, fallback):
        self._fallback = fallback

    def write(self, text):
        sink = getattr(_local, "sink", None)
        if sink is None:
            return self._fallback.write(text)
        sink(text)
        return len(text)

    def flush(self):
        self._fallback.flush()

    def __getattr__(self, name):
        return getattr(self._fallback, name)


def install():
    if not isinstance(sys.stdout, _ThreadRoutedStdout):
        sys.stdout = _ThreadRoutedStdout(sys.stdout)


class capture:
    """Context manager sending this thread's prints to ``sink(text)``."""

    def __init__(self, sink):
        self._sink = sink

    def __enter__(self):
        _local.sink = self._sink
        return self

    def __exit__(self, *exc):
        _local.sink = None
        return False
