"""Acompanhamento dos preenchimentos (fills) na conversa da partida.

O canal ``BR.Any`` é criado pelo Fortnite ao entrar na ilha. Os eventos
``Pl:``/``PlayerAdded`` adicionam os companheiros e ``PlayerRemoved`` os
remove. Quando o conjunto fica vazio, o bot pode sair da partida em vez de
continuar AFK sozinho.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SquadTracker:
    conversation: Optional[str] = None
    players: set[str] = field(default_factory=set)
    local_player: Optional[str] = None
    seen_players: bool = False

    def reset(self) -> None:
        """Esquece a partida atual, mantendo o ID do jogador local."""
        self.conversation = None
        self.players.clear()
        self.seen_players = False

    def on_match_chat(self, conversation: str) -> bool:
        """Seleciona o canal da partida; devolve True se for um canal novo."""
        if not conversation or conversation == self.conversation:
            return False
        self.conversation = conversation
        self.players.clear()
        self.seen_players = False
        return True

    def on_player_join(self, conversation: str, player: str) -> bool:
        """Adiciona um companheiro; devolve True se ele é novo."""
        if not conversation or conversation != self.conversation:
            return False
        if not player or player == self.local_player:
            return False
        if player in self.players:
            return False
        self.players.add(player)
        self.seen_players = True
        return True

    def on_player_leave(self, conversation: str, player: str) -> bool:
        """Remove um companheiro; devolve True se ele estava na lista."""
        if not conversation or conversation != self.conversation:
            return False
        if not player or player not in self.players:
            return False
        self.players.discard(player)
        return True

    def set_local_player(self, player: str) -> bool:
        """Registra o jogador local e o remove da lista, se necessário."""
        if not player:
            return False
        self.local_player = player
        if player in self.players:
            self.players.discard(player)
            return True
        return False

    @property
    def empty(self) -> bool:
        return not self.players
