"""Foco da janela e envio de cliques/teclas para o Fortnite."""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from typing import Callable, Optional

from .config import AppConfig
from .vision import GameWindow

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.mouse_event.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_size_t,
]
user32.mouse_event.restype = None
user32.keybd_event.argtypes = [
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.DWORD,
    ctypes.c_size_t,
]
user32.keybd_event.restype = None
user32.SwitchToThisWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.SwitchToThisWindow.restype = None
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9


class GameController:
    def __init__(
        self,
        window: GameWindow,
        config: AppConfig,
        dry_run: bool = False,
        logger: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.window = window
        self.config = config
        self.dry_run = dry_run
        self.logger = logger or (lambda message, level="info": None)

    @property
    def hwnd(self) -> int:
        return self.window.hwnd

    def is_foreground(self) -> bool:
        return user32.GetForegroundWindow() == self.hwnd

    def is_own_process_foreground(self) -> bool:
        foreground = user32.GetForegroundWindow()
        if not foreground:
            return False
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
        return process_id.value == os.getpid()

    def ensure_foreground(self, force: bool = False) -> bool:
        if self.is_foreground():
            return True
        if self.dry_run:
            return False
        if not force and self.is_own_process_foreground():
            return False
        try:
            if user32.IsIconic(self.hwnd):
                user32.ShowWindow(self.hwnd, SW_RESTORE)
                time.sleep(0.4)

            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.SetForegroundWindow(self.hwnd)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.25)
            if self.is_foreground():
                return True

            user32.SwitchToThisWindow(self.hwnd, True)
            time.sleep(0.25)
            if self.is_foreground():
                return True

            foreground = user32.GetForegroundWindow()
            foreground_pid = wintypes.DWORD()
            foreground_thread = user32.GetWindowThreadProcessId(
                foreground, ctypes.byref(foreground_pid)
            )
            game_pid = wintypes.DWORD()
            game_thread = user32.GetWindowThreadProcessId(
                self.hwnd, ctypes.byref(game_pid)
            )
            current_thread = kernel32.GetCurrentThreadId()

            user32.AttachThreadInput(current_thread, foreground_thread, True)
            user32.AttachThreadInput(current_thread, game_thread, True)
            user32.SetForegroundWindow(self.hwnd)
            user32.AttachThreadInput(current_thread, game_thread, False)
            user32.AttachThreadInput(current_thread, foreground_thread, False)
            time.sleep(0.25)
        except Exception as exc:
            self.logger(f"Falha ao focar o jogo: {exc}", "warn")

        return self.is_foreground()

    def focus_if_needed(self) -> bool:
        if self.is_foreground():
            return True
        if self.is_own_process_foreground():
            return False
        return self.ensure_foreground(force=False)

    def _to_screen(self, client_x: float, client_y: float) -> tuple[int, int]:
        self.window.refresh()
        return (
            self.window.client_x + int(round(client_x)),
            self.window.client_y + int(round(client_y)),
        )

    def _snapshot_context(self) -> tuple[int, Optional[tuple[int, int]]]:
        """Guarda a janela em primeiro plano e a posição do cursor."""
        try:
            foreground = int(user32.GetForegroundWindow() or 0)
        except Exception:
            foreground = 0
        cursor: Optional[tuple[int, int]] = None
        point = wintypes.POINT()
        try:
            if user32.GetCursorPos(ctypes.byref(point)):
                cursor = (int(point.x), int(point.y))
        except Exception:
            pass
        return foreground, cursor

    def _restore_context(self, snapshot: tuple[int, Optional[tuple[int, int]]]) -> None:
        """Devolve o foco e o cursor ao usuário depois de um clique rápido."""
        foreground, cursor = snapshot
        try:
            if (
                foreground
                and foreground != self.hwnd
                and self.is_foreground()
                and user32.IsWindow(foreground)
            ):
                if not user32.SetForegroundWindow(foreground):
                    user32.SwitchToThisWindow(foreground, True)
                time.sleep(0.05)
            if cursor is not None:
                user32.SetCursorPos(cursor[0], cursor[1])
        except Exception as exc:
            self.logger(f"Não consegui restaurar o foco anterior: {exc}", "debug")

    def _background_context(self) -> Optional[tuple[int, Optional[tuple[int, int]]]]:
        if not self.config.behavior.background_mode or self.dry_run:
            return None
        return self._snapshot_context()

    def click_client(self, client_x: float, client_y: float) -> bool:
        screen_x, screen_y = self._to_screen(client_x, client_y)
        if self.dry_run:
            self.logger(f"SIMULAÇÃO: clique em ({screen_x}, {screen_y}).", "debug")
            return True

        snapshot = self._background_context()
        if not self.ensure_foreground(force=True):
            if snapshot is not None:
                self._restore_context(snapshot)
            self.logger("Não consegui colocar o Fortnite em primeiro plano para clicar.", "warn")
            return False

        user32.SetCursorPos(screen_x, screen_y)
        time.sleep(0.06)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.07)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.15)
        if snapshot is not None:
            self._restore_context(snapshot)
        return True

    def click_ref(self, x: float, y: float) -> bool:
        self.window.refresh()
        scaled_x = x * self.window.width / self.config.game.ref_width
        scaled_y = y * self.window.height / self.config.game.ref_height
        return self.click_client(scaled_x, scaled_y)

    def _press_key(self, name: str, vk: int) -> bool:
        if self.dry_run:
            self.logger(f"SIMULAÇÃO: pressionaria {name.upper()}.", "debug")
            return True
        snapshot = self._background_context()
        if not self.ensure_foreground(force=True):
            if snapshot is not None:
                self._restore_context(snapshot)
            self.logger(f"Não consegui focar o jogo para pressionar {name.upper()}.", "warn")
            return False
        try:
            import pydirectinput

            pydirectinput.press(name)
        except Exception:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.2)
        if snapshot is not None:
            self._restore_context(snapshot)
        return True

    def press_enter(self) -> bool:
        return self._press_key("enter", VK_RETURN)

    def press_space(self) -> bool:
        return self._press_key("space", VK_SPACE)

    def press_escape(self) -> bool:
        return self._press_key("escape", VK_ESCAPE)
