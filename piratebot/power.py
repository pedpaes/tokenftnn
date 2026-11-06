"""Mantém o Windows acordado (sem suspensão nem desligamento de tela).

O estado de execução do Windows é por thread. Por isso um worker dedicado
chama SetThreadExecutionState periodicamente enquanto houver pelo menos um
motivo ativo ("manual" para o botão da interface e "bot" durante a execução).

Isso evita a suspensão automática e o desligamento da tela por inatividade,
que também podem bloquear a sessão. Bloqueio manual (Win+L) não é afetado.
"""
from __future__ import annotations

import ctypes
import threading
from typing import Optional

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

REFRESH_SECONDS = 25.0

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.SetThreadExecutionState.argtypes = [ctypes.c_ulong]
_kernel32.SetThreadExecutionState.restype = ctypes.c_ulong

_lock = threading.Lock()
_reasons: set[str] = set()
_thread: Optional[threading.Thread] = None
_wake = threading.Event()
_stopping = False


def _set_state(active: bool) -> bool:
    flags = ES_CONTINUOUS
    if active:
        flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    try:
        return bool(_kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False


def _worker() -> None:
    while True:
        with _lock:
            active = bool(_reasons)
            stopping = _stopping
        if stopping:
            _set_state(False)
            return
        _set_state(active)
        _wake.wait(REFRESH_SECONDS)
        _wake.clear()


def _ensure_thread() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _wake.clear()
        _thread = threading.Thread(target=_worker, name="KeepAwake", daemon=True)
        _thread.start()


def set_awake(reason: str, enabled: bool) -> bool:
    """Ativa/desativa a prevenção de suspensão para um motivo."""
    global _stopping
    with _lock:
        if enabled:
            _reasons.add(reason)
            _stopping = False
        else:
            _reasons.discard(reason)
        active = bool(_reasons)
    if active:
        _ensure_thread()
    _wake.set()
    return active


def is_awake() -> bool:
    with _lock:
        return bool(_reasons)


def reasons() -> set[str]:
    with _lock:
        return set(_reasons)


def shutdown() -> None:
    """Desliga o worker e libera o estado de execução do Windows."""
    global _stopping
    with _lock:
        _stopping = True
        _reasons.clear()
        thread = _thread
    _wake.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
