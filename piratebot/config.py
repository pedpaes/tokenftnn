"""Configuração do Pirate Farm.

As coordenadas em config.json são sempre relativas a 1920x1080. O controlador
faz a escala para o tamanho real da janela do jogo.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOGS = ROOT / "logs"
CONFIG_PATH = ROOT / "config.json"

T = TypeVar("T")


def _expand_path(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(str(value)))


def _pair(value: Any) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    raise ValueError(f"Coordenada inválida: {value!r} (esperado [x, y])")


def _int_tuple(value: Any) -> tuple[int, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(int(v) for v in value)
    raise ValueError(f"Lista de tamanhos inválida: {value!r}")


def _build(cls: type[T], data: dict[str, Any]) -> T:
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        default = f.default
        if f.name in (
            "play_tab",
            "play_button",
            "suspend_continue",
            "claim_button",
            "leave_match_confirm",
        ):
            value = _pair(value)
        elif f.name in ("inner_scales", "frame_scales"):
            value = _int_tuple(value)
        elif isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            value = int(value)
        elif isinstance(default, float):
            value = float(value)
        kwargs[f.name] = value
    return cls(**kwargs)


@dataclass
class GameConfig:
    window_title: str = "Fortnite"
    log_path: str = r"%LOCALAPPDATA%\FortniteGame\Saved\Logs\FortniteGame.log"
    ref_width: int = 1920
    ref_height: int = 1080


@dataclass
class UIConfig:
    play_tab: tuple[int, int] = (265, 68)
    play_button: tuple[int, int] = (265, 938)
    suspend_continue: tuple[int, int] = (960, 496)
    claim_button: tuple[int, int] = (965, 992)
    # (0, 0) = usa ENTER quando o jogo pedir confirmação para sair.
    leave_match_confirm: tuple[int, int] = (0, 0)


@dataclass
class DetectionConfig:
    downscale_width: int = 1280
    inner_scales: tuple[int, ...] = (60, 75, 95, 120, 150, 190, 240, 300, 380, 480, 600)
    frame_scales: tuple[int, ...] = (100, 125, 155, 195, 245, 305, 380)
    inner_score: float = 0.62
    inner_score_small: float = 0.62
    inner_small_width: int = 100
    frame_score: float = 0.70
    gold_min: float = 0.65
    white_min_inner: float = 0.20
    white_min_inner_small: float = 0.20
    white_max_inner: float = 0.80
    white_max_inner_small: float = 0.80
    gold_min_inner_small: float = 0.60
    white_min_frame: float = 0.08
    play_score: float = 0.80
    suspend_score: float = 0.80
    # Seta de saída no canto superior direito do menu de pausa (UI antiga).
    exit_icon_score: float = 0.60
    # Botão RETORNAR AO LOBBY na tela de resumo da partida.
    return_lobby_score: float = 0.65
    # Botão JOGAR NOVAMENTE na tela de resumo da partida.
    play_again_score: float = 0.65
    # Botão Voltar ao Lobby dentro do menu de pausa (UI nova).
    voltar_lobby_score: float = 0.62
    # Aba de três linhas que abre as opções de saída no painel social.
    menu_tab_score: float = 0.75


@dataclass
class BehaviorConfig:
    scan_interval_match: float = 1.6
    scan_interval_postmatch: float = 1.2
    focus_interval: float = 20.0
    ready_delay: float = 3.0
    matchmaking_timeout: float = 240.0
    # Espera a tela de resumo aparecer antes de clicar em JOGAR NOVAMENTE.
    postmatch_click_after: float = 8.0
    # Intervalo entre cliques caso o resumo não avance de imediato.
    postmatch_click_retry: float = 6.0
    # Se o resumo não mostrar nenhum botão (caso em que o jogador local foi o
    # último sobrevivente), espera esse tempo e abre o menu com ESC para usar
    # "Voltar ao Lobby".
    postmatch_menu_after: float = 14.0
    postmatch_timeout: float = 180.0
    claim_timeout: float = 20.0
    claim_scan_interval: float = 1.0
    # Tempo de espera antes de sair quando o último fill abandona a partida.
    # Se alguém voltar nesse intervalo, a saída é cancelada.
    squad_leave_delay: float = 10.0
    squad_leave_retry: float = 20.0
    squad_leave_max_attempts: int = 3
    max_matches: int = 0
    max_runtime_minutes: int = 0
    auto_close_success_seconds: int = 30
    dry_run: bool = False
    background_mode: bool = True


@dataclass
class AppConfig:
    game: GameConfig = field(default_factory=GameConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    cfg = AppConfig(
        game=_build(GameConfig, raw.get("game", {})),
        ui=_build(UIConfig, raw.get("ui", {})),
        detection=_build(DetectionConfig, raw.get("detection", {})),
        behavior=_build(BehaviorConfig, raw.get("behavior", {})),
    )
    cfg.game.log_path = _expand_path(cfg.game.log_path)
    return cfg


def save_config(cfg: AppConfig, path: Path = CONFIG_PATH) -> None:
    # O caminho padrão é expandido ao carregar; salve-o de volta na forma
    # portátil para o config.json continuar válido em outros computadores.
    game = dict(cfg.game.__dict__)
    default_log_path = GameConfig().log_path
    if game.get("log_path") == _expand_path(default_log_path):
        game["log_path"] = default_log_path

    data = {
        "game": game,
        "ui": cfg.ui.__dict__,
        "detection": cfg.detection.__dict__,
        "behavior": cfg.behavior.__dict__,
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
