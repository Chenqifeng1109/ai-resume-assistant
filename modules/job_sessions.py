"""Local, Windows-user-bound browser storage. Never infer login from cookies."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit


DOMAINS = {"51job": "51job.com", "liepin": "liepin.com"}
AUTH_STATES = {"unknown", "authenticated", "anonymous", "expired"}


def _crypt(data, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("Secure browser session storage requires Windows DPAPI")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    target = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    method = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    method.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("Browser session encryption/decryption failed")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(target.data)


class BrowserSessionStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path(
            os.environ.get("LOCALAPPDATA", str(Path.home()))
        ) / "OfferForge" / "browser_sessions"

    def _path(self, source):
        if source not in DOMAINS:
            raise ValueError("Unknown browser session source")
        return self.directory / f"{source}.dpapi"

    def _filter(self, source, state):
        self._path(source)
        root = DOMAINS[source]

        def allowed(host):
            host = host.lower().lstrip(".")
            return host == root or host.endswith("." + root)

        return {
            "cookies": [cookie for cookie in state.get("cookies", [])
                        if allowed(cookie.get("domain", ""))],
            "origins": [origin for origin in state.get("origins", [])
                        if urlsplit(origin.get("origin", "")).scheme == "https"
                        and allowed(urlsplit(origin.get("origin", "")).hostname or "")],
        }

    def save(self, source, state, auth_status="unknown"):
        if auth_status not in AUTH_STATES:
            raise ValueError("Invalid authentication state")
        path = self._path(source)
        payload = {"version": 1, "source": source, "saved_at": time.time(),
                   "auth_status": auth_status, "storage_state": self._filter(source, state)}
        encrypted = _crypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as target:
                temporary = target.name
                target.write(encrypted)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.remove(temporary)

    def _read(self, source):
        path = self._path(source)
        if not path.exists():
            return None
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("Invalid browser session size")
        payload = json.loads(_crypt(path.read_bytes(), decrypt=True))
        if payload.get("source") != source or payload.get("version") != 1:
            raise ValueError("Browser session identity mismatch")
        return payload

    def load(self, source):
        payload = self._read(source)
        if payload is None or payload.get("auth_status") == "expired":
            return None
        state = self._filter(source, payload["storage_state"])
        now = time.time()
        state["cookies"] = [cookie for cookie in state["cookies"]
                            if cookie.get("expires", -1) == -1 or cookie.get("expires", 0) > now]
        return state

    def status(self, source):
        try:
            payload = self._read(source)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            return {"storage_status": "unreadable", "auth_status": "unknown"}
        if payload is None:
            return {"storage_status": "missing", "auth_status": "unknown"}
        return {"storage_status": "saved", "auth_status": "unknown",
                "last_observed_auth_status": payload.get("auth_status", "unknown"),
                "saved_at": payload["saved_at"]}

    def clear(self, source):
        self._path(source).unlink(missing_ok=True)
