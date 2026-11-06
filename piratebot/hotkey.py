"""Atalho global F8 usando RegisterHotKey (sem hooks de teclado)."""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Optional

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL

MOD_NOREPEAT = 0x4000


class HotkeyListener:
    VK_F8 = 0x77

    def __init__(self, callback: Callable[[], None], vk: int = VK_F8) -> None:
        self.callback = callback
        self.vk = vk
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._ready = threading.Event()
        self._error: Optional[Exception] = None
        self._running = False

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._thread = threading.Thread(target=self._run, name="HotkeyListener", daemon=True)
        self._thread.start()
        if not self._ready.wait(3.0):
            self._error = RuntimeError("O atalho F8 não terminou de registrar a tempo.")
            return False
        return self._error is None

    @property
    def error(self) -> Optional[Exception]:
        return self._error

    def _run(self) -> None:
        try:
            import win32api
            import win32con
            import win32gui

            class_name = f"PirateFarmHotkey_{id(self)}"
            window_class = win32gui.WNDCLASS()
            window_class.lpszClassName = class_name
            window_class.hInstance = win32api.GetModuleHandle(None)
            window_class.lpfnWndProc = self._wndproc
            atom = win32gui.RegisterClass(window_class)
            self._hwnd = win32gui.CreateWindow(
                atom,
                "PirateFarmHotkey",
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                window_class.hInstance,
                None,
            )

            # O wrapper win32gui.RegisterHotKey falha em algumas versões do
            # pywin32; a chamada nativa abaixo é equivalente e confiável.
            if not user32.RegisterHotKey(self._hwnd, 1, MOD_NOREPEAT, self.vk):
                error_code = ctypes.get_last_error()
                detail = ctypes.FormatError(error_code) if error_code else "erro desconhecido"
                if error_code == 1409:
                    detail = "a tecla já está registrada por outro programa"
                raise RuntimeError(
                    f"RegisterHotKey(F8) falhou (código {error_code}: {detail})."
                )

            self._running = True
            self._ready.set()
            win32gui.PumpMessages()
        except Exception as exc:
            self._error = exc
            self._ready.set()
        finally:
            self._running = False

    def _wndproc(self, hwnd, message, wparam, lparam):
        import win32con
        import win32gui

        if message == win32con.WM_HOTKEY:
            try:
                self.callback()
            except Exception:
                pass
            return 0
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def stop(self) -> None:
        if self._hwnd:
            try:
                import win32con
                import win32gui

                user32.UnregisterHotKey(self._hwnd, 1)
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._hwnd = None
