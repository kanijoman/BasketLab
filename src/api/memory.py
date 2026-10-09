"""Optional per-request memory log (set ``LOG_MEMORY=1``) to find what pushes RSS up on Render.

Logs a WARNING for every request that grows the process RSS by more than ``LOG_MEMORY_DELTA_MB``
(default 25) or leaves it above ``LOG_MEMORY_HIGH_MB`` (default 350, ~70 % of the 512 MB limit).
"""
import logging
import os
import sys
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response

log = logging.getLogger("basketlab.memory")


def rss_mb() -> float:
    """Resident memory of this process in MB."""
    if sys.platform.startswith("linux"):
        with open("/proc/self/statm") as fh:
            return int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD]
        c = _Counters()
        c.cb = ctypes.sizeof(c)
        psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 1048576
    import resource  # macOS: peak RSS in bytes

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576


def install(app: FastAPI) -> None:
    """Add the middleware (a no-op per request unless LOG_MEMORY=1)."""

    @app.middleware("http")
    async def _memory_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if os.getenv("LOG_MEMORY") != "1":
            return await call_next(request)
        before = rss_mb()
        response = await call_next(request)
        after = rss_mb()
        delta_limit = float(os.getenv("LOG_MEMORY_DELTA_MB", "25"))
        high = float(os.getenv("LOG_MEMORY_HIGH_MB", "350"))
        if after - before >= delta_limit or after >= high:
            log.warning("%s %s rss %.0f MB (%+.0f MB)", request.method, request.url.path, after, after - before)
        return response
