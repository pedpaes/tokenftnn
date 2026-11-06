"""Diagnóstico visual do pós-partida e do menu de pausa.

Captura a janela do Fortnite em segundo plano e informa a confiança de cada
template conhecido. O script **não clica, não pressiona teclas e não rouba o
foco** do jogo.

Uso:
    .droxz\\Scripts\\python.exe tools\\check_postmatch.py
    .droxz\\Scripts\\python.exe tools\\check_postmatch.py --foreground
    .droxz\\Scripts\\python.exe tools\\check_postmatch.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from piratebot.config import ASSETS, LOGS, load_config
from piratebot.vision import (
    GameWindowNotFound,
    ScreenCaptureError,
    ScreenGrabber,
    TokenDetector,
    find_game_window,
    imwrite_u,
)


def inspect_frame(detector: TokenDetector, frame: Any) -> dict[str, dict[str, Any]]:
    """Devolve o resultado dos templates para um frame, sem efeitos colaterais."""
    detection = detector.detect(frame)
    best = detection.best
    result: dict[str, dict[str, Any]] = {
        "token": {
            "found": detection.found,
            "score": round(best.score, 4) if best is not None else 0.0,
            "center": best.center if best is not None else None,
            "size": (best.w, best.h) if best is not None else None,
        }
    }

    buttons = (
        ("jogar", detector.find_play_button(frame)),
        ("continuar_jogando", detector.find_suspend_button(frame)),
        ("jogar_novamente", detector.find_play_again_button(frame)),
        ("retornar_ao_lobby", detector.find_return_lobby_button(frame)),
        ("voltar_ao_lobby", detector.find_voltar_lobby_button(frame)),
        ("aba_menu", detector.find_menu_tab_button(frame)),
        ("seta_saida", detector.find_exit_button(frame)),
    )
    for name, hit in buttons:
        result[name] = {
            "found": hit is not None,
            "score": round(hit.score, 4) if hit is not None else 0.0,
            "center": hit.center if hit is not None else None,
            "size": (hit.w, hit.h) if hit is not None else None,
        }
    return result


def _capture(title: str, foreground: bool) -> tuple[Any, Any]:
    window = find_game_window(title)
    grabber = ScreenGrabber(window)
    frame = grabber.capture() if foreground else grabber.capture_background()
    return window, frame


def _print_report(results: dict[str, dict[str, Any]], output: Path) -> None:
    labels = {
        "token": "Token Pirate Shop",
        "jogar": "JOGAR",
        "continuar_jogando": "CONTINUAR JOGANDO",
        "jogar_novamente": "JOGAR NOVAMENTE",
        "retornar_ao_lobby": "RETORNAR AO LOBBY",
        "voltar_ao_lobby": "Voltar ao Lobby (menu)",
        "aba_menu": "Aba de opções (três linhas)",
        "seta_saida": "Seta de saída (UI antiga)",
    }
    print()
    print("Template                   Resultado   Confiança   Centro")
    print("-" * 70)
    for name, label in labels.items():
        item = results[name]
        status = "SIM" if item["found"] else "não"
        center = item["center"] or "-"
        print(f"{label:<26} {status:<11} {item['score']:>8.3f}   {center}")
    print()
    print(f"Captura salva em: {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico visual do pós-partida do Fortnite (não clica)."
    )
    parser.add_argument(
        "--title",
        default="Fortnite",
        help="Parte do título da janela do jogo (padrão: Fortnite).",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Captura pela tela em primeiro plano em vez de PrintWindow.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o resultado em JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=LOGS / "diagnostico_pos_partida.png",
        help="Caminho da captura de diagnóstico.",
    )
    args = parser.parse_args(argv)

    config = load_config()
    detector = TokenDetector(ASSETS, config.detection)

    try:
        window, frame = _capture(args.title, args.foreground)
    except GameWindowNotFound as exc:
        print(f"Janela não encontrada: {exc}", file=sys.stderr)
        return 1
    except ScreenCaptureError as exc:
        print(f"Falha na captura: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    imwrite_u(args.output, frame)
    results = inspect_frame(detector, frame)

    if args.json:
        payload = {
            "window": {
                "title": window.title,
                "width": window.width,
                "height": window.height,
            },
            "capture": "primeiro plano" if args.foreground else "segundo plano",
            "output": str(args.output),
            "templates": results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print()
        print("Pirate Farm — diagnóstico do pós-partida")
        print(f"Janela: {window.title} ({window.width}x{window.height})")
        print(
            "Captura: "
            + ("primeiro plano" if args.foreground else "segundo plano (PrintWindow)")
        )
        _print_report(results, args.output)

    if not any(item["found"] for item in results.values()):
        print()
        print(
            "Nenhum template conhecido foi encontrado. Abra o resumo da partida "
            "ou o menu de pausa e tente novamente.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
