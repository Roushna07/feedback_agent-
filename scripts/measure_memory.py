"""
measure_memory.py — measure process RSS before/after loading the local NLLB
translation model. Used for the Streamlit Community Cloud free-tier
resource assessment (1 GB RAM budget).

Usage:
    python scripts/measure_memory.py

Reports baseline RSS, RSS after model load, and the model's memory delta.
Read-only: never touches the database or patient data.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _rss_mb() -> float:
    """Current process resident set size in MB (Windows + POSIX)."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        fn = ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                       wintypes.DWORD]
        fn.restype = wintypes.BOOL
        if fn(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    try:
        import resource  # POSIX
        # ru_maxrss is KB on Linux, bytes on macOS
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss / 1024.0 if sys.platform != "darwin" else rss / (1024 * 1024)
    except Exception:
        return -1.0


def main() -> int:
    baseline = _rss_mb()
    print(f"baseline RSS: {baseline:.1f} MB")

    print("loading local NLLB (CTranslate2 int8) translation model ...")
    started = time.time()
    try:
        from services.translation import OfflineNeuralTranslator
        translator = OfflineNeuralTranslator.get_instance()
        elapsed = time.time() - started
    except Exception as exc:
        print(f"model load FAILED: {exc}")
        print(f"RSS after failure: {_rss_mb():.1f} MB")
        return 1

    loaded = _rss_mb()
    print(f"model load time: {elapsed:.1f} s")
    print(f"RSS after model load: {loaded:.1f} MB")
    print(f"model memory delta: {loaded - baseline:.1f} MB")
    if getattr(translator, "load_error", None):
        print(f"load_error: {translator.load_error}")
        return 1

    # One real translation to confirm the loaded model works
    text, err = translator.translate_sentence(
        "स्वास्थ्यकर्मी ने मुझे इलाज अच्छी तरह समझाया।", "hi", "en")
    print(f"sample translation: {text!r} (err={err!r})")
    print(f"final RSS: {_rss_mb():.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
