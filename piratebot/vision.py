"""Captura de tela, localização da janela e detecção visual do token."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mss
import numpy as np

try:
    import win32gui
except ImportError:  # pragma: no cover
    win32gui = None

from .config import DetectionConfig


class GameWindowNotFound(RuntimeError):
    pass


class ScreenCaptureError(RuntimeError):
    pass


# --------------------------------------------------------------- Win32/GDI
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

_user32.GetWindowDC.argtypes = [wintypes.HWND]
_user32.GetWindowDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
_user32.PrintWindow.restype = wintypes.BOOL
_user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetClientRect.restype = wintypes.BOOL

_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_gdi32.DeleteDC.restype = wintypes.BOOL
_gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.c_void_p,
    wintypes.UINT,
]
_gdi32.GetDIBits.restype = ctypes.c_int

PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BitmapInfoHeader),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def imread_u(path: str | Path) -> Optional[np.ndarray]:
    """cv2.imread não aceita acentos no caminho do Windows; este lê por bytes."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_u(path: str | Path, image: np.ndarray) -> bool:
    path = Path(path)
    try:
        extension = path.suffix or ".png"
        ok, buffer = cv2.imencode(extension, image)
        if not ok:
            return False
        buffer.tofile(str(path))
        return True
    except Exception:
        return False


def gold_ratio(bgr: np.ndarray) -> float:
    if bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 70, 70), (42, 255, 255))
    return float((mask > 0).mean())


def white_ratio_center(bgr: np.ndarray) -> float:
    if bgr.size == 0:
        return 0.0
    height, width = bgr.shape[:2]
    center = bgr[int(height * 0.28) : int(height * 0.72), int(width * 0.28) : int(width * 0.72)]
    if center.size == 0:
        return 0.0
    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 170), (180, 95, 255))
    return float((mask > 0).mean())


@dataclass
class Hit:
    kind: str
    score: float
    x: int
    y: int
    w: int
    h: int
    gold: float
    white: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass
class Detection:
    found: bool
    hits: list[Hit]
    elapsed_ms: float

    @property
    def best(self) -> Optional[Hit]:
        return self.hits[0] if self.hits else None


@dataclass
class ButtonHit:
    score: float
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def _nms(hits: list[tuple[float, int, int, int, int, str]], ratio: float = 0.45):
    kept = []
    for hit in sorted(hits, key=lambda item: -item[0]):
        score, x, y, width, height, kind = hit
        center_x, center_y = x + width / 2, y + height / 2
        duplicate = False
        for other in kept:
            _, ox, oy, ow, oh, _ = other
            ocx, ocy = ox + ow / 2, oy + oh / 2
            if (
                abs(center_x - ocx) < min(width, ow) * ratio
                and abs(center_y - ocy) < min(height, oh) * ratio
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(hit)
    return kept


class TokenDetector:
    """Detecta a moeda dourada do Pirate Shop Access.

    A moeda é procurada em duas formas:
      - inner: disco dourado com o "F" branco (tela de recompensa)
      - frame: quadro dourado do banner durante a partida
    """

    def __init__(self, assets: str | Path, config: DetectionConfig) -> None:
        self.assets = Path(assets)
        self.config = config

        self.inner = self._load("coin_inner.png")
        self.frame = self._load("coin_banner_frame.png")
        self.play_button = self._load("play_button.png")
        self.suspend_button = self._load("suspend_button.png")
        try:
            self.exit_icon = self._load("exit_icon.png")
        except FileNotFoundError:
            # Instalações antigas podem não ter o template novo; a saída
            # automática simplesmente fica indisponível.
            self.exit_icon = None
        try:
            self.return_lobby = self._load("return_lobby.png")
        except FileNotFoundError:
            self.return_lobby = None
        try:
            self.play_again = self._load("play_again.png")
        except FileNotFoundError:
            self.play_again = None
        try:
            self.voltar_lobby = self._load("voltar_lobby.png")
        except FileNotFoundError:
            self.voltar_lobby = None
        try:
            self.menu_tab = self._load("menu_tab.png")
        except FileNotFoundError:
            self.menu_tab = None

        self._inner_gray = cv2.cvtColor(self.inner, cv2.COLOR_BGR2GRAY)
        self._frame_gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)

    def _load(self, name: str) -> np.ndarray:
        path = self.assets / name
        image = imread_u(path)
        if image is None:
            raise FileNotFoundError(f"Template não encontrado ou inválido: {path}")
        return image

    def detect(self, image: np.ndarray) -> Detection:
        started = time.perf_counter()
        height, width = image.shape[:2]
        if width <= 0 or height <= 0:
            return Detection(False, [], 0.0)

        scale = min(1.0, self.config.downscale_width / width)
        if scale < 1.0:
            small = cv2.resize(
                image,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            small = image

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        raw_hits: list[tuple[float, int, int, int, int, str]] = []

        jobs = (
            ("inner", self._inner_gray, self.config.inner_scales),
            ("frame", self._frame_gray, self.config.frame_scales),
        )

        for kind, template_gray, scales in jobs:
            for reference_width in scales:
                template_width = int(round(reference_width * scale))
                template_height = int(round(template_gray.shape[0] * template_width / template_gray.shape[1]))
                if (
                    template_width < 35
                    or template_height < 35
                    or template_width >= gray.shape[1]
                    or template_height >= gray.shape[0]
                ):
                    continue

                threshold = self.config.inner_score if kind == "inner" else self.config.frame_score
                if kind == "inner" and template_width < self.config.inner_small_width:
                    threshold = self.config.inner_score_small

                template = cv2.resize(
                    template_gray, (template_width, template_height), interpolation=cv2.INTER_AREA
                )
                result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(result >= threshold)
                for y, x in zip(ys, xs):
                    y0, y1 = max(0, y - 2), min(result.shape[0], y + 3)
                    x0, x1 = max(0, x - 2), min(result.shape[1], x + 3)
                    if result[y, x] >= result[y0:y1, x0:x1].max() - 1e-6:
                        raw_hits.append(
                            (
                                float(result[y, x]),
                                int(x),
                                int(y),
                                template_width,
                                template_height,
                                kind,
                            )
                        )

        valid: list[Hit] = []
        for score, x, y, width_small, height_small, kind in _nms(raw_hits):
            crop = small[y : y + height_small, x : x + width_small]
            if crop.size == 0:
                continue
            gold = gold_ratio(crop)
            white = white_ratio_center(crop)

            if kind == "inner":
                if width_small < self.config.inner_small_width:
                    ok = (
                        score >= self.config.inner_score_small
                        and gold >= self.config.gold_min_inner_small
                        and white >= self.config.white_min_inner_small
                        and white <= self.config.white_max_inner_small
                    )
                else:
                    ok = (
                        score >= self.config.inner_score
                        and gold >= self.config.gold_min
                        and white >= self.config.white_min_inner
                        and white <= self.config.white_max_inner
                    )
            else:
                ok = (
                    score >= self.config.frame_score
                    and gold >= self.config.gold_min
                    and white >= self.config.white_min_frame
                )

            if ok:
                valid.append(
                    Hit(
                        kind=kind,
                        score=score,
                        x=int(round(x / scale)),
                        y=int(round(y / scale)),
                        w=int(round(width_small / scale)),
                        h=int(round(height_small / scale)),
                        gold=gold,
                        white=white,
                    )
                )

        valid.sort(key=lambda hit: -hit.score)
        elapsed = (time.perf_counter() - started) * 1000.0
        return Detection(bool(valid), valid, elapsed)

    def _find_button(
        self,
        image: np.ndarray,
        template: np.ndarray,
        score_min: float,
        region: Optional[tuple[int, int, int, int]] = None,
        base_width: int = 1920,
        factors: tuple[float, ...] = (0.85, 0.925, 1.0, 1.075, 1.15),
    ) -> Optional[ButtonHit]:
        height, width = image.shape[:2]
        if region is None:
            x0, y0, x1, y1 = 0, 0, width, height
        else:
            x0, y0, x1, y1 = region
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(width, x1), min(height, y1)
        if x1 <= x0 or y1 <= y0:
            return None

        roi = image[y0:y1, x0:x1]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        base_scale = width / base_width

        best = ButtonHit(0.0, 0, 0, 0, 0)
        for factor in factors:
            scale = base_scale * factor
            tw = int(round(template_gray.shape[1] * scale))
            th = int(round(template_gray.shape[0] * scale))
            if tw < 20 or th < 10 or tw >= gray.shape[1] or th >= gray.shape[0]:
                continue
            resized = cv2.resize(template_gray, (tw, th), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_value, _, max_location = cv2.minMaxLoc(result)
            if max_value > best.score:
                best = ButtonHit(
                    score=float(max_value),
                    x=x0 + max_location[0],
                    y=y0 + max_location[1],
                    w=tw,
                    h=th,
                )

        return best if best.score >= score_min else None

    def find_play_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        height, width = image.shape[:2]
        region = (0, int(height * 0.62), int(width * 0.58), height)
        return self._find_button(
            image, self.play_button, self.config.play_score, region=region
        )

    def find_suspend_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        return self._find_button(image, self.suspend_button, self.config.suspend_score)

    def find_return_lobby_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        """Localiza o botão RETORNAR AO LOBBY na tela de resumo da partida."""
        if self.return_lobby is None:
            return None
        height, width = image.shape[:2]
        region = (
            int(width * 0.55),
            int(height * 0.30),
            width,
            int(height * 0.60),
        )
        return self._find_button(
            image,
            self.return_lobby,
            self.config.return_lobby_score,
            region=region,
        )

    def find_play_again_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        """Localiza o botão JOGAR NOVAMENTE na tela de resumo da partida.

        A busca fica restrita à metade direita e à faixa vertical dos botões
        grandes do resumo, para não confundir com elementos do HUD.
        """
        if self.play_again is None:
            return None
        height, width = image.shape[:2]
        region = (
            int(width * 0.55),
            int(height * 0.35),
            width,
            int(height * 0.65),
        )
        return self._find_button(
            image,
            self.play_again,
            self.config.play_again_score,
            region=region,
        )

    def find_voltar_lobby_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        """Localiza o botão Voltar ao Lobby dentro do menu de pausa.

        Na interface nova o menu não tem mais a seta de saída: o primeiro
        botão da aba do menu já é ``Voltar ao Lobby``. A busca fica no topo
        da metade direita, onde esse painel aparece.
        """
        if self.voltar_lobby is None:
            return None
        height, width = image.shape[:2]
        region = (
            int(width * 0.55),
            int(height * 0.08),
            width,
            int(height * 0.30),
        )
        return self._find_button(
            image,
            self.voltar_lobby,
            self.config.voltar_lobby_score,
            region=region,
        )

    def find_menu_tab_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        """Localiza a aba de três linhas do painel social.

        No menu novo, ESC abre o painel social. O botão **Voltar ao Lobby**
        só aparece depois de clicar nessa aba; por isso ela é procurada no
        canto superior direito da tela.
        """
        if self.menu_tab is None:
            return None
        height, width = image.shape[:2]
        region = (
            int(width * 0.80),
            int(height * 0.02),
            int(width * 0.95),
            int(height * 0.14),
        )
        return self._find_button(
            image,
            self.menu_tab,
            self.config.menu_tab_score,
            region=region,
        )

    @property
    def exit_icon_width(self) -> int:
        if self.exit_icon is None:
            return 0
        return int(self.exit_icon.shape[1])

    def find_exit_button(self, image: np.ndarray) -> Optional[ButtonHit]:
        """Localiza a seta de saída no canto superior direito do menu.

        O menu social do Fortnite fica ancorado à direita. A busca é limitada
        ao canto superior direito para não confundir a seta com ícones do HUD.
        """
        if self.exit_icon is None:
            return None
        height, width = image.shape[:2]
        region = (int(width * 0.55), 0, width, max(1, int(height * 0.25)))
        return self._find_button(
            image,
            self.exit_icon,
            self.config.exit_icon_score,
            region=region,
            factors=(
                0.65,
                0.75,
                0.85,
                0.925,
                1.0,
                1.075,
                1.15,
                1.3,
                1.45,
                1.6,
                1.8,
            ),
        )


@dataclass
class GameWindow:
    hwnd: int
    title: str
    client_x: int
    client_y: int
    width: int
    height: int

    def monitor(self) -> dict:
        return {
            "left": self.client_x,
            "top": self.client_y,
            "width": self.width,
            "height": self.height,
        }

    def refresh(self) -> None:
        """Atualiza posição/tamanho caso a janela tenha sido movida ou redimensionada."""
        if win32gui is None:
            return
        try:
            if not win32gui.IsWindow(self.hwnd):
                return
            left, top = win32gui.ClientToScreen(self.hwnd, (0, 0))
            _, _, width, height = win32gui.GetClientRect(self.hwnd)
            if width >= 100 and height >= 100:
                self.client_x, self.client_y = left, top
                self.width, self.height = width, height
        except Exception:
            pass


def find_game_window(title_filter: str = "Fortnite") -> GameWindow:
    if win32gui is None:
        raise GameWindowNotFound("pywin32 não está instalado corretamente.")

    candidates: list[tuple[int, GameWindow, str]] = []
    fallback: list[tuple[int, GameWindow, str]] = []
    wanted = title_filter.strip().lower()

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title or wanted not in title.lower():
            return
        class_name = win32gui.GetClassName(hwnd)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width < 800 or height < 600:
            return
        client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
        _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
        window = GameWindow(
            hwnd=hwnd,
            title=title,
            client_x=client_left,
            client_y=client_top,
            width=client_width,
            height=client_height,
        )
        area = client_width * client_height
        if class_name == "UnrealWindow":
            candidates.append((area, window, class_name))
        else:
            fallback.append((area, window, class_name))

    win32gui.EnumWindows(callback, None)

    chosen = candidates or fallback
    if not chosen:
        raise GameWindowNotFound(
            "Janela do Fortnite não encontrada. Abra o jogo e deixe-o em primeiro plano."
        )

    _, window, _ = max(chosen, key=lambda item: item[0])
    return window


class ScreenGrabber:
    def __init__(self, window: GameWindow) -> None:
        self.window = window

    def is_foreground(self) -> bool:
        return bool(win32gui) and win32gui.GetForegroundWindow() == self.window.hwnd

    def capture(self) -> np.ndarray:
        self.window.refresh()
        if win32gui is not None and win32gui.IsIconic(self.window.hwnd):
            raise ScreenCaptureError("A janela do Fortnite está minimizada.")
        try:
            with mss.mss() as sct:
                shot = sct.grab(self.window.monitor())
                frame = np.asarray(shot, dtype=np.uint8)
        except Exception as exc:
            raise ScreenCaptureError(f"Falha ao capturar a tela: {exc}") from exc
        if frame.ndim != 3:
            raise ScreenCaptureError("Captura de tela inválida.")
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def capture_background(self) -> np.ndarray:
        """Captura a janela mesmo encoberta, sem trazê-la para a frente.

        Usa PrintWindow com PW_RENDERFULLCONTENT, que pede ao jogo (DWM) para
        renderizar o conteúdo completo em um bitmap. Funciona com o Fortnite em
        modo janela sem borda e não minimizado; tela cheia exclusiva não é
        suportada pelo Windows para captura em segundo plano.
        """
        if win32gui is None:
            raise ScreenCaptureError("pywin32 não está instalado corretamente.")
        self.window.refresh()
        hwnd = self.window.hwnd
        try:
            if not win32gui.IsWindow(hwnd):
                raise ScreenCaptureError("A janela do Fortnite não está mais disponível.")
            if win32gui.IsIconic(hwnd):
                raise ScreenCaptureError(
                    "A janela do Fortnite está minimizada. Restaure-a para usar o modo segundo plano."
                )
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            window_width, window_height = right - left, bottom - top
            if window_width < 100 or window_height < 100:
                raise ScreenCaptureError(
                    "A janela do Fortnite está sem tamanho válido para captura."
                )
        except ScreenCaptureError:
            raise
        except Exception as exc:
            raise ScreenCaptureError(f"Falha ao obter a janela do Fortnite: {exc}") from exc

        window_dc = _user32.GetWindowDC(hwnd)
        if not window_dc:
            raise ScreenCaptureError("Não consegui obter o contexto da janela do Fortnite.")
        memory_dc = _gdi32.CreateCompatibleDC(window_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(window_dc, window_width, window_height)
        if not memory_dc or not bitmap:
            if bitmap:
                _gdi32.DeleteObject(bitmap)
            if memory_dc:
                _gdi32.DeleteDC(memory_dc)
            _user32.ReleaseDC(hwnd, window_dc)
            raise ScreenCaptureError("Não consegui criar o bitmap de captura.")

        old_object = _gdi32.SelectObject(memory_dc, bitmap)
        try:
            ok = bool(_user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT))
            if not ok:
                ok = bool(_user32.PrintWindow(hwnd, memory_dc, 0))
            if not ok:
                raise ScreenCaptureError(
                    "O Windows não conseguiu renderizar a janela do Fortnite. "
                    "Use o modo janela sem borda e não minimize o jogo."
                )

            bmi = _BitmapInfo()
            header = bmi.bmiHeader
            header.biSize = ctypes.sizeof(_BitmapInfoHeader)
            header.biWidth = window_width
            header.biHeight = -window_height  # negativo = linhas de cima para baixo
            header.biPlanes = 1
            header.biBitCount = 32
            header.biCompression = BI_RGB
            buffer = ctypes.create_string_buffer(window_width * window_height * 4)

            # A documentação do GetDIBits pede que o bitmap não esteja
            # selecionado no DC na hora da leitura.
            _gdi32.SelectObject(memory_dc, old_object)
            old_object = None
            lines = _gdi32.GetDIBits(
                memory_dc,
                bitmap,
                0,
                window_height,
                buffer,
                ctypes.byref(bmi),
                0,
            )
            if lines == 0:
                raise ScreenCaptureError("Falha ao ler os pixels da janela do Fortnite.")

            frame = np.frombuffer(buffer, dtype=np.uint8).reshape(
                (window_height, window_width, 4)
            )
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
            _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
            crop_x = max(0, client_left - left)
            crop_y = max(0, client_top - top)
            crop_width = min(client_width, window_width - crop_x)
            crop_height = min(client_height, window_height - crop_y)
            if crop_width >= 100 and crop_height >= 100:
                frame = frame[crop_y : crop_y + crop_height, crop_x : crop_x + crop_width]
            return frame
        finally:
            if old_object is not None:
                _gdi32.SelectObject(memory_dc, old_object)
            _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(memory_dc)
            _user32.ReleaseDC(hwnd, window_dc)
