"""Interface gráfica do Droxz Farm."""
from __future__ import annotations

import ctypes
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

# Deixa as coordenadas em pixels físicos (importante em telas com escala).
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from piratebot import power
from piratebot.bot import PHASE_LABELS, Phase, PirateBot
from piratebot.config import ASSETS, LOGS, ROOT, load_config, save_config
from piratebot.hotkey import HotkeyListener
from piratebot.vision import (
    ScreenGrabber,
    TokenDetector,
    find_game_window,
    imwrite_u,
)

APP_TITLE = "Droxz Farm — Fortnite"
APP_VERSION = "1.1.4"

# Paleta do modo escuro.
BG = "#0a0f18"
BG_SOFT = "#0e1624"
CARD = "#101a2a"
CARD_BORDER = "#1e2b40"
SUBTLE = "#162235"
SUBTLE_HOVER = "#1f3049"
TEXT = "#e8eef8"
MUTED = "#94a7c0"
DIM = "#5f728c"
GOLD = "#f4c95d"
GREEN = "#34d399"
GREEN_DARK = "#0f766e"
GREEN_DEEP = "#123c33"
RED = "#f87171"
RED_DARK = "#8f1d1d"
AMBER = "#fbbf24"
BLUE = "#60a5fa"

PHASE_STYLE = {
    Phase.STARTING.value: ("Iniciando...", BLUE),
    Phase.LOBBY.value: ("No lobby", BLUE),
    Phase.QUEUING.value: ("Procurando partida", "#c084fc"),
    Phase.MATCH.value: ("Em partida — AFK", "#2dd4bf"),
    Phase.POSTMATCH.value: ("Fim de partida", AMBER),
    Phase.FINISHED.value: ("TOKEN ENCONTRADO!", "#4ade80"),
    Phase.ERROR.value: ("Erro", RED),
    Phase.STOPPED.value: ("Parado", "#94a3b8"),
}


def _format_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PirateFarmApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.ui_queue: "queue.Queue[dict]" = queue.Queue()
        self.stop_event = threading.Event()
        self.manual_token = threading.Event()
        self.bot: PirateBot | None = None
        self.hotkey: HotkeyListener | None = None
        self._logs_opened = False
        self._success_scheduled = False
        self._log_line_count = 0
        self._manual_awake = False
        self._last_power_refresh = 0.0
        self._build_ui()
        self._start_hotkey()
        self.root.after(100, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("760x720")
        self.root.minsize(680, 600)
        self.root.configure(bg=BG)

        try:
            icon = tk.PhotoImage(file=str(ASSETS / "logo_256.png"))
            self.root.iconphoto(True, icon)
            self._icon = icon
        except Exception:
            pass

        container = tk.Frame(self.root, bg=BG, padx=20, pady=16)
        container.pack(fill="both", expand=True)

        # ---------------------------------------------------------- cabeçalho
        header = tk.Frame(container, bg=BG)
        header.pack(fill="x", pady=(0, 12))
        try:
            self._header_logo = tk.PhotoImage(file=str(ASSETS / "logo_64.png"))
            tk.Label(header, image=self._header_logo, bg=BG).pack(side="left", padx=(0, 14))
        except Exception:
            self._header_logo = None

        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(
            titles,
            text="Droxz Farm",
            font=("Segoe UI", 23, "bold"),
            fg=TEXT,
            bg=BG,
        ).pack(anchor="w")
        tk.Label(
            titles,
            text=f"Farm AFK do token Pirate Shop Access · Fortnite · v{APP_VERSION}",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(1, 0))
        tk.Label(
            header,
            text="PT-BR",
            font=("Segoe UI", 8, "bold"),
            fg="#86efac",
            bg=GREEN_DEEP,
            padx=8,
            pady=4,
        ).pack(side="right", anchor="n")

        # ------------------------------------------------------------- status
        status_card = tk.Frame(
            container,
            bg=CARD,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        status_card.pack(fill="x")

        self.status_label = tk.Label(
            status_card,
            text="Pronto para iniciar",
            font=("Segoe UI", 18, "bold"),
            fg=MUTED,
            bg=CARD,
            anchor="w",
        )
        self.status_label.pack(fill="x")

        self.detail_label = tk.Label(
            status_card,
            text=(
                "Abra o Fortnite no lobby, com Battle Royale e Squad + Fill, "
                "e clique em INICIAR."
            ),
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=CARD,
            anchor="w",
            justify="left",
            wraplength=670,
        )
        self.detail_label.pack(fill="x", pady=(3, 10))

        stats = tk.Frame(status_card, bg=CARD)
        stats.pack(fill="x")
        self.matches_label = tk.Label(
            stats,
            text="Partidas: 0",
            font=("Segoe UI", 10, "bold"),
            fg="#cbd5e1",
            bg=CARD,
        )
        self.matches_label.pack(side="left")
        self.token_label = tk.Label(
            stats,
            text="Token: não",
            font=("Segoe UI", 10, "bold"),
            fg=RED,
            bg=CARD,
        )
        self.token_label.pack(side="left", padx=(24, 0))
        self.time_label = tk.Label(
            stats,
            text="Tempo: 00:00:00",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=CARD,
        )
        self.time_label.pack(side="right")

        # ----------------------------------------------------------- controles
        controls = tk.Frame(container, bg=BG)
        controls.pack(fill="x", pady=(14, 8))

        self.start_button = tk.Button(
            controls,
            text="INICIAR",
            font=("Segoe UI", 12, "bold"),
            bg="#15803d",
            fg="#ffffff",
            activebackground="#166534",
            activeforeground="#ffffff",
            disabledforeground="#64748b",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=24,
            pady=10,
            cursor="hand2",
            command=self._start_bot,
        )
        self.start_button.pack(side="left")

        self.stop_button = tk.Button(
            controls,
            text="PARAR (F8)",
            font=("Segoe UI", 11, "bold"),
            bg=RED_DARK,
            fg="#ffffff",
            activebackground="#7f1d1d",
            activeforeground="#ffffff",
            disabledforeground="#64748b",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=18,
            pady=10,
            cursor="hand2",
            state="disabled",
            command=lambda: self._stop_bot("Parado pelo usuário."),
        )
        self.stop_button.pack(side="left", padx=(10, 0))

        self.token_button = tk.Button(
            controls,
            text="Já tenho o token",
            font=("Segoe UI", 10, "bold"),
            bg=GOLD,
            fg="#1c1917",
            activebackground="#d97706",
            activeforeground="#1c1917",
            disabledforeground="#64748b",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=15,
            pady=10,
            cursor="hand2",
            state="disabled",
            command=self._mark_token,
        )
        self.token_button.pack(side="left", padx=(10, 0))

        # ------------------------------------------------------------ opções
        options = tk.Frame(container, bg=BG)
        options.pack(fill="x", pady=(0, 8))

        self.bg_var = tk.BooleanVar(value=self.config.behavior.background_mode)
        self.sim_var = tk.BooleanVar(value=self.config.behavior.dry_run)
        self.bg_chip = self._chip(
            options, "Segundo plano", self.bg_var, command=self._update_mode_hint
        )
        self.bg_chip.pack(side="left")
        self.sim_chip = self._chip(options, "Simulação", self.sim_var)
        self.sim_chip.pack(side="left", padx=(8, 0))

        self.power_button = tk.Button(
            options,
            text="○  Manter PC acordado",
            font=("Segoe UI", 9, "bold"),
            bg=SUBTLE,
            fg=MUTED,
            activebackground=SUBTLE_HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=11,
            pady=6,
            cursor="hand2",
            command=self._toggle_keep_awake,
        )
        self.power_button.pack(side="right")
        self.power_label = tk.Label(
            options,
            text="PC acordado: não",
            font=("Segoe UI", 9),
            fg=DIM,
            bg=BG,
        )
        self.power_label.pack(side="right", padx=(0, 10))

        # ------------------------------------------------------------- tools
        tools = tk.Frame(container, bg=BG)
        tools.pack(fill="x", pady=(0, 10))
        self._tool_button(tools, "Testar detecção agora", self._test_detection).pack(
            side="left"
        )
        self._tool_button(tools, "Abrir logs", self._open_logs).pack(
            side="left", padx=(8, 0)
        )
        self._tool_button(tools, "Limpar registro", self._clear_log).pack(
            side="left", padx=(8, 0)
        )
        tk.Label(
            tools,
            text="F8 = parada de emergência",
            font=("Segoe UI", 9),
            fg=DIM,
            bg=BG,
        ).pack(side="right")

        # -------------------------------------------------------- dica de modo
        self.mode_hint_card = tk.Frame(
            container,
            bg="#10243a",
            highlightbackground="#1e3a5f",
            highlightthickness=1,
            padx=13,
            pady=9,
        )
        self.mode_hint_card.pack(fill="x", pady=(0, 10))
        self.mode_hint = tk.Label(
            self.mode_hint_card,
            text="",
            font=("Segoe UI", 9),
            fg="#bfdbfe",
            bg="#10243a",
            anchor="w",
            justify="left",
            wraplength=670,
        )
        self.mode_hint.pack(fill="x")
        self._update_mode_hint()

        # --------------------------------------------------------------- log
        log_header = tk.Frame(container, bg=BG)
        log_header.pack(fill="x")
        tk.Label(
            log_header,
            text="REGISTRO",
            font=("Segoe UI", 9, "bold"),
            fg=MUTED,
            bg=BG,
        ).pack(side="left")
        tk.Label(
            log_header,
            text="tudo é gravado em logs\\piratefarm_*.log",
            font=("Segoe UI", 8),
            fg=DIM,
            bg=BG,
        ).pack(side="right")

        log_frame = tk.Frame(
            container,
            bg="#08101d",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame,
            height=14,
            wrap="word",
            bg="#08101d",
            fg="#dbe7f5",
            insertbackground="#dbe7f5",
            selectbackground="#1d4ed8",
            font=("Consolas", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=8,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.tag_config("ts", foreground="#64748b")
        self.log_text.tag_config("info", foreground="#dbe7f5")
        self.log_text.tag_config("success", foreground="#6ee7b7")
        self.log_text.tag_config("warn", foreground="#fbbf24")
        self.log_text.tag_config("error", foreground="#f87171")
        self.log_text.tag_config("debug", foreground="#7c8ba1")
        self.log_text.configure(state="disabled")

        footer = tk.Frame(container, bg=BG)
        footer.pack(fill="x", pady=(8, 0))
        tk.Label(
            footer,
            text="100% local · sem acesso à internet",
            font=("Segoe UI", 8),
            fg=DIM,
            bg=BG,
        ).pack(side="left")
        tk.Label(
            footer,
            text="Squad Fill · interface em português",
            font=("Segoe UI", 8),
            fg=DIM,
            bg=BG,
        ).pack(side="right")

        # A barra de título só aceita o modo escuro depois que a janela é
        # realmente mapeada e ativada pelo Windows; reaplicamos ao mapear e
        # sempre que a janela ganha foco (o DWM descarta a cor no primeiro
        # desenho se ela for definida cedo demais).
        self.root.after(120, self._focus_window)
        self.root.bind(
            "<Map>",
            lambda _event: self.root.after(
                250, lambda: self._apply_dark_titlebar(self.root)
            ),
        )
        self.root.bind(
            "<FocusIn>",
            lambda _event: self._apply_dark_titlebar(self.root),
        )
        for delay in (350, 1500, 3000):
            self.root.after(delay, lambda: self._apply_dark_titlebar(self.root))

    # ------------------------------------------------------------- widgets
    def _chip(self, parent, text: str, variable: tk.BooleanVar, command=None):
        button = tk.Button(
            parent,
            font=("Segoe UI", 9, "bold"),
            bg=SUBTLE,
            fg=MUTED,
            activebackground=SUBTLE_HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=11,
            pady=6,
            cursor="hand2",
            anchor="w",
        )

        def refresh() -> None:
            selected = bool(variable.get())
            button.config(
                text=("●  " if selected else "○  ") + text,
                bg=GREEN_DEEP if selected else SUBTLE,
                fg="#86efac" if selected else MUTED,
                activebackground=GREEN_DEEP if selected else SUBTLE_HOVER,
                activeforeground="#bbf7d0" if selected else TEXT,
            )

        def toggle() -> None:
            variable.set(not variable.get())
            refresh()
            if command is not None:
                command()

        button.config(command=toggle)
        refresh()
        return button

    def _tool_button(self, parent, text: str, command):
        return tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 9),
            bg=SUBTLE,
            fg="#cbd5e1",
            activebackground=SUBTLE_HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=command,
        )

    def _update_mode_hint(self) -> None:
        if not hasattr(self, "mode_hint"):
            return
        if self.bg_var.get():
            card_bg, border, foreground = "#10243a", "#1e3a5f", "#bfdbfe"
            text = (
                "Segundo plano ativo: você pode usar o PC durante as partidas. "
                "O Fortnite não pode estar minimizado nem em tela cheia exclusiva — "
                "use janela sem borda. O bot traz o jogo à frente por ~1s apenas "
                "para clicar e devolve o foco ao seu programa."
            )
        else:
            card_bg, border, foreground = "#2a2110", "#713f12", "#fde68a"
            text = (
                "Modo primeiro plano: deixe o Fortnite na frente e não use o PC "
                "durante o farm. Se o jogo perder o foco, o bot tenta clicar em "
                "CONTINUAR JOGANDO."
            )
        self.mode_hint_card.config(bg=card_bg, highlightbackground=border)
        self.mode_hint.config(text=text, bg=card_bg, fg=foreground)

    def _focus_window(self) -> None:
        """Traz o app para a frente ao abrir e ativa a barra de título escura."""
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def _apply_dark_titlebar(self, window: tk.Misc) -> None:
        try:
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
            dwm = ctypes.windll.dwmapi
            enabled = ctypes.c_int(1)
            for attribute in (20, 19):
                if dwm.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
                ) == 0:
                    break
            caption = ctypes.c_int(0x0020120B)  # COLORREF de #0b1220
            dwm.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption)
            )
            text = ctypes.c_int(0x00F9EEE6)  # COLORREF de #e6eef9
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
            border = ctypes.c_int(0x004B3122)  # COLORREF de #22314b
            dwm.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(border), ctypes.sizeof(border)
            )
        except Exception:
            pass

    def _center_dialog(self, dialog: tk.Toplevel) -> None:
        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 2)
        dialog.geometry(f"+{x}+{y}")

    def _dialog(self, title: str, message: str, confirm: bool = False) -> bool:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        resultado = {"ok": False}

        body = tk.Frame(dialog, bg=BG, padx=22, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text=title,
            font=("Segoe UI", 13, "bold"),
            fg=TEXT,
            bg=BG,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text=message,
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BG,
            justify="left",
            wraplength=460,
            anchor="w",
        ).pack(fill="x", pady=(8, 18))

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x")

        def close(value: bool) -> None:
            resultado["ok"] = value
            dialog.destroy()

        if confirm:
            tk.Button(
                buttons,
                text="Cancelar",
                font=("Segoe UI", 9, "bold"),
                bg=SUBTLE,
                fg="#cbd5e1",
                activebackground=SUBTLE_HOVER,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=16,
                pady=7,
                cursor="hand2",
                command=lambda: close(False),
            ).pack(side="right")
            tk.Button(
                buttons,
                text="Sim, parar",
                font=("Segoe UI", 9, "bold"),
                bg=RED_DARK,
                fg="#ffffff",
                activebackground="#7f1d1d",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=16,
                pady=7,
                cursor="hand2",
                command=lambda: close(True),
            ).pack(side="right", padx=(0, 8))
        else:
            tk.Button(
                buttons,
                text="OK",
                font=("Segoe UI", 9, "bold"),
                bg=GREEN_DARK,
                fg="#ffffff",
                activebackground="#115e59",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=20,
                pady=7,
                cursor="hand2",
                command=lambda: close(True),
            ).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
        dialog.bind("<Escape>", lambda _event: close(False))
        if not confirm:
            dialog.bind("<Return>", lambda _event: close(True))
        self._center_dialog(dialog)
        dialog.bind(
            "<FocusIn>",
            lambda _event: self._apply_dark_titlebar(dialog),
        )
        dialog.after(80, lambda: self._apply_dark_titlebar(dialog))
        dialog.after(600, lambda: self._apply_dark_titlebar(dialog))
        dialog.wait_window()
        return resultado["ok"]

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log_line_count = 0
        self._log("Registro limpo.", "debug")

    # ------------------------------------------------------------- energia
    def _toggle_keep_awake(self) -> None:
        self._manual_awake = not self._manual_awake
        power.set_awake("manual", self._manual_awake)
        self._refresh_power_ui()
        if self._manual_awake:
            self._log(
                "Prevenção de suspensão ativada: o Windows não vai dormir nem "
                "desligar a tela por inatividade.",
                "success",
            )
        else:
            self._log(
                "Prevenção de suspensão manual desativada. O bot ainda mantém o "
                "PC acordado enquanto estiver rodando.",
                "info",
            )

    def _refresh_power_ui(self) -> None:
        if not hasattr(self, "power_button"):
            return
        selected = bool(self._manual_awake)
        self.power_button.config(
            text=("●  " if selected else "○  ") + "Manter PC acordado",
            bg=GREEN_DEEP if selected else SUBTLE,
            fg="#86efac" if selected else MUTED,
            activebackground=GREEN_DEEP if selected else SUBTLE_HOVER,
            activeforeground="#bbf7d0" if selected else TEXT,
        )
        active = power.is_awake()
        if active:
            reasons = power.reasons()
            if "bot" in reasons and "manual" in reasons:
                origin = "manual + bot"
            elif "bot" in reasons:
                origin = "automático"
            else:
                origin = "manual"
            self.power_label.config(text=f"PC acordado: sim ({origin})", fg=GREEN)
        else:
            self.power_label.config(text="PC acordado: não", fg=DIM)

    def _start_hotkey(self) -> None:
        self.hotkey = HotkeyListener(lambda: self.ui_queue.put({"type": "hotkey"}))
        if not self.hotkey.start():
            error = self.hotkey.error
            self._log(
                f"Não consegui registrar o atalho F8 ({error}). Use o botão PARAR.",
                "warn",
            )

    # --------------------------------------------------------------- ações
    def _start_bot(self) -> None:
        if self.bot is not None and self.bot.is_running():
            return
        self.stop_event.clear()
        self.manual_token.clear()
        self._success_scheduled = False
        self.config.behavior.dry_run = bool(self.sim_var.get())
        self.config.behavior.background_mode = bool(self.bg_var.get())
        try:
            save_config(self.config)
        except Exception as exc:
            self._log(f"Não consegui salvar as preferências: {exc}", "debug")

        self.bot = PirateBot(
            self.config,
            self.ui_queue,
            self.stop_event,
            self.manual_token,
        )
        self._log(
            "Bot iniciado"
            + (" em modo SIMULAÇÃO." if self.config.behavior.dry_run else "."),
            "success",
        )
        if not self.config.behavior.dry_run:
            if self.config.behavior.background_mode:
                self._log(
                    "Modo segundo plano ativo: captura sem roubar o foco e foco "
                    "rápido de ~1s apenas para clicar. Não minimize o Fortnite.",
                    "success",
                )
            else:
                self._log(
                    "Modo primeiro plano: não use o PC enquanto o bot estiver rodando.",
                    "warn",
                )
        self.bot.start()
        self._update_buttons()
        self._refresh_power_ui()

    def _stop_bot(self, reason: str) -> None:
        self.stop_event.set()
        if self.bot is not None:
            self.bot.stop()
        self._log(reason, "warn")
        self._set_status(Phase.STOPPED.value, reason)
        self._update_buttons()
        self._refresh_power_ui()

    def _mark_token(self) -> None:
        if self.bot is None or not self.bot.is_running():
            self._log("O bot não está rodando.", "warn")
            return
        self.manual_token.set()
        self._log(
            "Token marcado manualmente. Vou aguardar o fim da partida "
            "(se houver) e encerrar.",
            "success",
        )
        self._set_status(
            Phase.MATCH.value,
            "Token marcado manualmente. Aguardando o fim da partida...",
        )

    def _test_detection(self) -> None:
        use_background = bool(self.bg_var.get())
        mode = "em segundo plano" if use_background else "em primeiro plano"
        self._log(f"Capturando a tela {mode} para testar a detecção...", "info")
        threading.Thread(
            target=self._run_detection_test,
            args=(use_background,),
            name="DetectionTest",
            daemon=True,
        ).start()

    def _run_detection_test(self, use_background: bool) -> None:
        try:
            window = find_game_window(self.config.game.window_title)
            grabber = ScreenGrabber(window)
            detector = TokenDetector(ASSETS, self.config.detection)
            frame = (
                grabber.capture_background()
                if use_background
                else grabber.capture()
            )
            token = detector.detect(frame)
            play = detector.find_play_button(frame)
            suspend = detector.find_suspend_button(frame)
            LOGS.mkdir(parents=True, exist_ok=True)
            path = LOGS / "teste_tela.png"
            imwrite_u(path, frame)
            self.ui_queue.put(
                {
                    "type": "test_result",
                    "token": token.found,
                    "best": token.best,
                    "game_foreground": grabber.is_foreground(),
                    "background": use_background,
                    "play": play,
                    "suspend": suspend,
                    "path": str(path),
                    "size": (frame.shape[1], frame.shape[0]),
                }
            )
        except Exception as exc:
            self.ui_queue.put({"type": "test_error", "text": str(exc)})

    def _open_logs(self) -> None:
        LOGS.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(LOGS))
        except Exception as exc:
            self._log(f"Não consegui abrir a pasta de logs: {exc}", "error")

    # ---------------------------------------------------------------- poll
    def _poll(self) -> None:
        while True:
            try:
                message = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_message(message)
        self._update_buttons()
        now = time.time()
        if now - self._last_power_refresh >= 0.5:
            self._last_power_refresh = now
            self._refresh_power_ui()
        self.root.after(100, self._poll)

    def _handle_message(self, message: dict) -> None:
        kind = message.get("type")

        if kind == "log":
            self._log(message.get("text", ""), message.get("level", "info"))

        elif kind == "status":
            phase = message.get("phase", Phase.STARTING.value)
            detail = message.get("message", "")
            self._set_status(phase, detail)
            self.matches_label.config(text=f"Partidas: {message.get('matches', 0)}")
            token = bool(message.get("token_found"))
            self.token_label.config(
                text="Token: SIM" if token else "Token: não",
                fg=GREEN if token else RED,
            )
            self.time_label.config(
                text=f"Tempo: {_format_elapsed(message.get('elapsed', 0))}"
            )

        elif kind == "token":
            self.token_label.config(text="Token: SIM", fg=GREEN)
            self._set_status(
                Phase.MATCH.value,
                "Token detectado! Vou esperar a partida terminar para encerrar.",
            )

        elif kind == "success":
            text = message.get("text", "Token encontrado!")
            self._set_status(Phase.FINISHED.value, text)
            self.token_label.config(text="Token: SIM", fg=GREEN)
            self._log(text, "success")
            self._write_success_file(text)
            self._schedule_auto_close()

        elif kind == "error":
            text = message.get("text", "Erro desconhecido.")
            self._set_status(Phase.ERROR.value, text)
            self.root.bell()
            try:
                self._dialog("Erro no Pirate Farm", text)
            except Exception:
                pass

        elif kind == "stopped":
            text = message.get("text", "Parado.")
            self._set_status(Phase.STOPPED.value, text)

        elif kind == "hotkey":
            if self.bot is not None and self.bot.is_running():
                self._stop_bot("Parada de emergência (F8).")
            else:
                self._log("F8 pressionado, mas o bot não está rodando.", "info")

        elif kind == "test_result":
            self._handle_test_result(message)

        elif kind == "test_error":
            text = message.get("text", "Falha no teste.")
            self._log(f"Teste de detecção falhou: {text}", "error")
            self._set_status(Phase.ERROR.value, f"Teste falhou: {text}")

    def _handle_test_result(self, message: dict) -> None:
        width, height = message.get("size", (0, 0))
        foreground = message.get("game_foreground")
        background = bool(message.get("background"))
        self._log(f"Captura de teste: {width}x{height}.", "info")
        if background:
            self._log(
                "Captura em segundo plano concluída; o foco do jogo não foi alterado.",
                "info",
            )
        elif not foreground:
            self._log(
                "A janela do Fortnite não estava em primeiro plano; "
                "a captura pode mostrar outra janela.",
                "warn",
            )

        if message.get("token"):
            best = message.get("best")
            if best is not None:
                self._log(
                    f"TOKEN VISÍVEL na tela! ({best.kind}, confiança {best.score:.2f}, "
                    f"{best.w}x{best.h})",
                    "success",
                )
            self._set_status(
                Phase.FINISHED.value,
                "Token visível na tela! Se estiver em partida, o bot vai aguardar o fim.",
            )
        else:
            self._log("Token não visível na captura (normal fora da tela de recompensa).", "info")

        play = message.get("play")
        if play is not None:
            self._log(
                f"Botão JOGAR detectado (confiança {play.score:.2f}) em ({play.x}, {play.y}).",
                "info",
            )
        else:
            self._log("Botão JOGAR não detectado.", "info")

        suspend = message.get("suspend")
        if suspend is not None:
            self._log(
                f"Botão CONTINUAR JOGANDO detectado (confiança {suspend.score:.2f}).",
                "warn",
            )
        else:
            self._log("Tela de suspensão não detectada.", "info")

        self._log(f"Captura salva em {message.get('path')}.", "debug")

        if not message.get("token") and play is None and suspend is None:
            self._set_status(
                Phase.LOBBY.value,
                "Teste concluído: nenhum elemento conhecido na captura. "
                "Traga o Fortnite para a frente e teste de novo.",
            )
        elif play is not None and not message.get("token"):
            self._set_status(
                Phase.LOBBY.value,
                "Teste concluído: lobby detectado. O bot está pronto para jogar.",
            )
        elif suspend is not None:
            self._set_status(
                Phase.STARTING.value,
                "Teste concluído: tela de suspensão detectada.",
            )

    # ------------------------------------------------------------- helpers
    def _set_status(self, phase: str, detail: str) -> None:
        label, color = PHASE_STYLE.get(phase, (PHASE_LABELS.get(phase, phase), MUTED))
        self.status_label.config(text=label, fg=color)
        self.detail_label.config(text=detail)

    def _log(self, text: str, level: str = "info") -> None:
        if not text:
            return
        tag = level if level in ("info", "success", "warn", "error", "debug") else "info"
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] ", "ts")
        self.log_text.insert("end", f"{text}\n", tag)
        self._log_line_count += 1
        if self._log_line_count > 2500:
            self.log_text.delete("1.0", "600.0")
            self._log_line_count -= 599
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_buttons(self) -> None:
        running = bool(self.bot is not None and self.bot.is_running())
        if running:
            self.start_button.config(
                state="disabled",
                bg="#123524",
                fg="#5f7a6b",
                disabledforeground="#5f7a6b",
                cursor="arrow",
            )
            self.stop_button.config(
                state="normal",
                bg=RED_DARK,
                fg="#ffffff",
                cursor="hand2",
            )
            self.token_button.config(
                state="normal",
                bg=GOLD,
                fg="#1c1917",
                cursor="hand2",
            )
        else:
            self.start_button.config(
                state="normal",
                bg="#15803d",
                fg="#ffffff",
                cursor="hand2",
            )
            self.stop_button.config(
                state="disabled",
                bg="#3a1a1a",
                fg="#8a6a6a",
                disabledforeground="#8a6a6a",
                cursor="arrow",
            )
            self.token_button.config(
                state="disabled",
                bg="#3a2f16",
                fg="#8a7a55",
                disabledforeground="#8a7a55",
                cursor="arrow",
            )

    def _write_success_file(self, text: str) -> None:
        try:
            stamp = time.strftime("%d/%m/%Y %H:%M:%S")
            (ROOT / "TOKEN_ENCONTRADO.txt").write_text(
                f"{text}\nDetectado em: {stamp}\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _schedule_auto_close(self) -> None:
        if self._success_scheduled:
            return
        self._success_scheduled = True
        seconds = int(self.config.behavior.auto_close_success_seconds)
        if seconds <= 0:
            return
        self._log(f"O programa vai fechar em {seconds} segundos.", "info")
        self.root.after(seconds * 1000, lambda: self._on_close(force=True))

    def _on_close(self, force: bool = False) -> None:
        if not force and self.bot is not None and self.bot.is_running():
            if not self._dialog(
                "Sair do Pirate Farm",
                "O bot está rodando. Deseja parar o farm e sair?",
                confirm=True,
            ):
                return
        self.stop_event.set()
        if self.bot is not None:
            self.bot.stop()
        if self.hotkey is not None:
            self.hotkey.stop()
        power.set_awake("manual", False)
        power.shutdown()
        self.root.destroy()


def _configure_logging() -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    path = LOGS / f"piratefarm_{time.strftime('%Y%m%d_%H%M%S')}.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    return path


def main() -> int:
    log_path = _configure_logging()

    def exception_hook(exc_type, exc_value, exc_traceback):
        logging.error("Falha não tratada", exc_info=(exc_type, exc_value, exc_traceback))
        try:
            messagebox.showerror(
                APP_TITLE,
                f"Ocorreu um erro inesperado:\n\n{exc_value}\n\nLog: {log_path}",
            )
        except Exception:
            pass

    sys.excepthook = exception_hook
    root = tk.Tk()
    app = PirateFarmApp(root)
    app._log(f"Log desta sessão: {log_path}", "debug")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
