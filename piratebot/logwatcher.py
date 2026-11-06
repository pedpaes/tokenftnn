"""Leitor incremental do FortniteGame.log.

O log do Fortnite é a fonte de verdade para o ciclo lobby -> partida -> lobby.
A visão computacional cuida apenas do token e das telas de recompensa.
"""
from __future__ import annotations

import os
import queue
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_UI_RE = re.compile(r"UI State changing from \[(.*?)\] to \[(.*?)\]")
_MATCH_RE = re.compile(r"Match State Changed from (\w+) to (\w+)")
_PHASE_RE = re.compile(r"EAthenaGamePhase::(\w+)")
_READY_RE = re.compile(r"await_barrier_requested.*BarrierId=\[ReadyUp\]")

# Canal de chat da partida. O Fortnite cria esse canal ao entrar na ilha e
# adiciona/remove os companheiros de esquadrão (fills) conforme eles entram e
# saem. É a fonte mais confiável para saber quando todos abandonaram a partida.
_MATCH_CHAT_RE = re.compile(
    r"LogSocialChatManager:.*?ChannelName:BR\.Any\..*?"
    r"Conversation:\[(?P<conversation>[^\]]+)\]"
)
_SQUAD_RE = re.compile(
    r"LogSocialChatManager:.*?Conversation:\[(?P<conversation>[^\]]+)\].*?"
    r"(?P<kind>Pl:|PlayerAdded:MCP:|PlayerRemoved:MCP:)"
    r"(?P<player>[0-9a-fA-F]+(?:\.\.\.[0-9a-fA-F]+)?)"
)
_LOCAL_PLAYER_RE = re.compile(
    r"SetHasFinishedLoading.*?Player:\s*MCP:(?P<player>[0-9a-fA-F]+)"
)
# Emitido após a morte do jogador local quando não há mais ninguém vivo no
# esquadrão. É o sinal de que o resumo pode não exibir JOGAR NOVAMENTE e de
# que a saída correta é ESC -> "Voltar ao Lobby".
_NO_TEAMMATES_RE = re.compile(
    r"LogSpectateAfterDeathViewTarget:.*?No teammates available to follow"
)

STATE_LOBBY = "lobby"
STATE_MATCH = "match"
STATE_LOGIN = "login"
STATE_TRANSITION = "transition"
STATE_OTHER = "other"

STATE_LABELS = {
    STATE_LOBBY: "lobby",
    STATE_MATCH: "partida",
    STATE_LOGIN: "tela de login",
    STATE_TRANSITION: "transição",
    STATE_OTHER: "outra tela",
    "unknown": "desconhecido",
}


@dataclass(frozen=True)
class LogEvent:
    kind: str
    value: str
    line: str
    when: float


def _ui_state(value: str) -> str:
    value = value.strip()
    if value.endswith("UI.State.Athena.Frontend"):
        return STATE_LOBBY
    if value.endswith("UI.State.Athena.BattleRoyale"):
        return STATE_MATCH
    if value.endswith("UI.State.Athena.Startup.Login"):
        return STATE_LOGIN
    if value in ("None", "[]", ""):
        return STATE_TRANSITION
    return STATE_OTHER


def player_key(player_id: str) -> str:
    """Normaliza IDs completos e truncados do log para a mesma chave.

    O `Pl:` traz o ID completo (32 caracteres), enquanto `PlayerAdded` e
    `PlayerRemoved` trazem a forma curta ``004b4...374e1``. Os dois formatos
    precisam ser comparáveis para acompanhar a saída dos preenchimentos.
    """
    value = player_id.strip().lower()
    if "..." in value or len(value) <= 12:
        return value
    return f"{value[:5]}...{value[-5:]}"


def parse_line(line: str, when: Optional[float] = None) -> Optional[LogEvent]:
    """Converte uma linha do log em um evento, ou None se não interessar."""
    when = time.time() if when is None else when

    match = _UI_RE.search(line)
    if match:
        return LogEvent("state", _ui_state(match.group(2)), line, when)

    match = _MATCH_RE.search(line)
    if match:
        return LogEvent("matchstate", match.group(2), line, when)

    match = _PHASE_RE.search(line)
    if match:
        return LogEvent("phase", match.group(1), line, when)

    if "LogSocialChatManager" in line:
        match = _MATCH_CHAT_RE.search(line)
        if match:
            return LogEvent("match_chat", match.group("conversation"), line, when)

        match = _SQUAD_RE.search(line)
        if match:
            kind = (
                "squad_leave"
                if match.group("kind").startswith("PlayerRemoved")
                else "squad_join"
            )
            value = f"{match.group('conversation')}|{player_key(match.group('player'))}"
            return LogEvent(kind, value, line, when)

    match = _LOCAL_PLAYER_RE.search(line)
    if match:
        return LogEvent("local_player", player_key(match.group("player")), line, when)

    if "WBP_PostMatchPanelContainer" in line:
        return LogEvent("postmatch", "", line, when)

    if "OnPlayerPawnDied" in line:
        return LogEvent("player_died", "", line, when)

    if _NO_TEAMMATES_RE.search(line):
        return LogEvent("no_teammates", "", line, when)

    if _READY_RE.search(line):
        return LogEvent("readyup", "", line, when)

    return None


class LogWatcher(threading.Thread):
    """Lê apenas o que for acrescentado ao log depois de prepare()."""

    TAIL_BYTES = 8_000_000

    def __init__(
        self,
        path: str | Path,
        event_queue: "queue.Queue[LogEvent]",
        stop_event: threading.Event,
        logger: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__(name="LogWatcher", daemon=True)
        self.path = Path(path)
        self.event_queue = event_queue
        self.stop_event = stop_event
        self.logger = logger or (lambda message, level="info": None)
        self._fh = None
        self._pos = 0
        self._ctime = 0.0
        self._prepared = False

    def prepare(self) -> str:
        """Abre o log no fim e devolve o estado atual (lobby/match/unknown)."""
        if not self.path.exists():
            raise FileNotFoundError(f"Log do Fortnite não encontrado: {self.path}")
        self._fh = open(self.path, "rb")
        self._fh.seek(0, os.SEEK_END)
        self._pos = self._fh.tell()
        self._ctime = self.path.stat().st_ctime
        self._prepared = True
        return self.read_initial_state()

    def read_initial_state(self) -> str:
        if not self.path.exists():
            return "unknown"
        size = self.path.stat().st_size
        start = max(0, size - self.TAIL_BYTES)
        with open(self.path, "rb") as fh:
            fh.seek(start)
            data = fh.read()
        if start:
            newline = data.find(b"\n")
            if newline != -1:
                data = data[newline + 1 :]

        last = "unknown"
        for raw in data.splitlines():
            event = parse_line(raw.decode("utf-8", "replace"))
            if event and event.kind == "state" and event.value in (STATE_LOBBY, STATE_MATCH):
                last = event.value
        return last

    def run(self) -> None:
        if not self._prepared:
            try:
                self.prepare()
            except Exception as exc:  # pragma: no cover - depende do ambiente
                self.logger(f"LogWatcher: {exc}", "error")
                return

        fh = self._fh
        while not self.stop_event.is_set():
            try:
                line = fh.readline()
            except Exception:
                line = b""

            if line:
                if not line.endswith(b"\n"):
                    # Linha parcial no fim do arquivo: volta e espera o resto.
                    fh.seek(self._pos)
                    time.sleep(0.1)
                    continue
                self._pos = fh.tell()
                text = line.decode("utf-8", "replace").rstrip("\r\n")
                event = parse_line(text)
                if event:
                    self.event_queue.put(event)
                continue

            time.sleep(0.25)
            try:
                stat = self.path.stat()
            except OSError:
                continue

            reset = stat.st_size < self._pos or stat.st_ctime != self._ctime
            if reset:
                try:
                    fh.close()
                except Exception:
                    pass
                try:
                    fh = open(self.path, "rb")
                    self._pos = 0
                    self._ctime = self.path.stat().st_ctime
                    self.event_queue.put(LogEvent("log_reset", "", "", time.time()))
                    self.logger("O log do Fortnite foi reiniciado.", "warn")
                except Exception:
                    time.sleep(1.0)

        try:
            fh.close()
        except Exception:
            pass
