"""Gera a identidade visual do projeto (logo, banner e social preview).

Uso:
    .droxz\\Scripts\\python.exe -m pip install -r requirements-dev.txt
    .droxz\\Scripts\\python.exe tools\\make_branding.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"

FONT_DIR = Path("C:/Windows/Fonts")
NAVY_TOP = (10, 17, 32)
NAVY_BOTTOM = (19, 33, 58)
GOLD_LIGHT = (255, 226, 145)
GOLD = (245, 196, 81)
GOLD_DARK = (176, 116, 25)
IVORY = (250, 240, 218)
DARK = (18, 24, 38)
GREEN = (52, 211, 153)
MUTED = (138, 160, 189)
TEXT = (219, 231, 245)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf")
        if bold
        else ("segoeui.ttf", "segoeuil.ttf", "arial.ttf")
    )
    for name in names:
        path = FONT_DIR / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def _linear_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    angle: float = 90.0,
) -> Image.Image:
    width, height = size
    radians = math.radians(angle)
    y, x = np.mgrid[0:height, 0:width]
    projection = x * math.cos(radians) + y * math.sin(radians)
    projection = (projection - projection.min()) / max(1e-6, projection.max() - projection.min())
    top_color = np.array(top, dtype=float)
    bottom_color = np.array(bottom, dtype=float)
    pixels = top_color + (bottom_color - top_color) * projection[..., None]
    return Image.fromarray(pixels.astype(np.uint8), "RGB").convert("RGBA")


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _disc_gradient(
    diameter: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    angle: float = 45.0,
) -> Image.Image:
    gradient = _linear_gradient((diameter, diameter), top, bottom, angle=angle)
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    gradient.putalpha(mask)
    return gradient


def _sparkle(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, color: tuple[int, int, int, int]):
    draw.polygon(
        [
            (cx, cy - radius),
            (cx + radius // 4, cy - radius // 4),
            (cx + radius, cy),
            (cx + radius // 4, cy + radius // 4),
            (cx, cy + radius),
            (cx - radius // 4, cy + radius // 4),
            (cx - radius, cy),
            (cx - radius // 4, cy - radius // 4),
        ],
        fill=color,
    )


def draw_skull(layer: Image.Image, cx: int, cy: int, scale: float) -> None:
    """Desenha caveira com ossos cruzados em uma camada RGBA."""
    draw = ImageDraw.Draw(layer)

    # Ossos cruzados atrás da caveira, encostando na borda dourada.
    bones_size = 460
    bones = Image.new("RGBA", (bones_size, bones_size), (0, 0, 0, 0))
    bone_color = (216, 188, 142, 255)
    for angle in (40, -40):
        bone = Image.new("RGBA", (330, 58), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bone)
        bd.rounded_rectangle((36, 12, 294, 46), radius=17, fill=bone_color)
        bd.ellipse((8, 2, 64, 56), fill=bone_color)
        bd.ellipse((266, 2, 322, 56), fill=bone_color)
        bone = bone.rotate(angle, resample=Image.BICUBIC, expand=True)
        bones.alpha_composite(bone, (bones_size // 2 - bone.width // 2, bones_size // 2 - bone.height // 2))
    layer.alpha_composite(bones, (cx - bones_size // 2, cy - bones_size // 2))

    def box(x0, y0, x1, y1):
        return (
            cx + int(x0 * scale),
            cy + int(y0 * scale),
            cx + int(x1 * scale),
            cy + int(y1 * scale),
        )

    # Crânio e mandíbula.
    draw.ellipse(box(-96, -116, 96, 58), fill=IVORY)
    draw.rounded_rectangle(box(-56, 22, 56, 104), radius=int(28 * scale), fill=IVORY)

    # Olhos, nariz, boca e dentes.
    draw.ellipse(box(-64, -60, -17, -9), fill=DARK)
    draw.ellipse(box(17, -60, 64, -9), fill=DARK)
    draw.polygon(
        [
            (cx, cy + int(-2 * scale)),
            (cx - int(15 * scale), cy + int(36 * scale)),
            (cx + int(15 * scale), cy + int(36 * scale)),
        ],
        fill=DARK,
    )
    draw.line(
        (cx - int(38 * scale), cy + int(60 * scale), cx + int(38 * scale), cy + int(60 * scale)),
        fill=DARK,
        width=max(3, int(5 * scale)),
    )
    for offset in (-32, -11, 11, 32):
        draw.line(
            (
                cx + int(offset * scale),
                cy + int(60 * scale),
                cx + int(offset * scale),
                cy + int(94 * scale),
            ),
            fill=DARK,
            width=max(3, int(4 * scale)),
        )


def make_logo(size: int = 512) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = _rounded_mask((size, size), int(size * 0.22))
    background = _linear_gradient((size, size), NAVY_TOP, NAVY_BOTTOM, angle=115)
    canvas.paste(background, (0, 0), mask)

    # Brilho suave atrás da moeda.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        (int(size * 0.12), int(size * 0.12), int(size * 0.88), int(size * 0.88)),
        fill=(245, 196, 81, 70),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(int(size * 0.07)))
    glow.putalpha(Image.composite(glow.getchannel("A"), Image.new("L", (size, size), 0), mask))
    canvas.alpha_composite(glow)

    center = size // 2
    coin = int(size * 0.72)
    coin_image = _disc_gradient(coin, GOLD_LIGHT, GOLD_DARK, angle=45)
    coin_mask = coin_image.getchannel("A")
    coin_layer = Image.new("RGBA", (coin, coin), (0, 0, 0, 0))
    coin_layer.paste(coin_image, (0, 0), coin_mask)
    cd = ImageDraw.Draw(coin_layer)

    rim = int(size * 0.012)
    cd.ellipse((rim, rim, coin - rim, coin - rim), outline=(255, 239, 188, 235), width=max(3, size // 90))
    cd.ellipse(
        (int(coin * 0.075), int(coin * 0.075), int(coin * 0.925), int(coin * 0.925)),
        outline=(122, 78, 17, 220),
        width=max(2, size // 110),
    )
    # Pequenos pontos de dublão.
    dot_radius = coin // 2 - int(size * 0.052)
    for index in range(36):
        angle = math.tau * index / 36
        x = coin // 2 + int(math.cos(angle) * dot_radius)
        y = coin // 2 + int(math.sin(angle) * dot_radius)
        r = max(1, size // 150)
        cd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 235, 170, 150))

    inner = int(coin * 0.80)
    face = _disc_gradient(inner, (228, 164, 54), (130, 82, 16), angle=80)
    coin_layer.alpha_composite(face, ((coin - inner) // 2, (coin - inner) // 2))

    skull_layer = Image.new("RGBA", (coin, coin), (0, 0, 0, 0))
    draw_skull(skull_layer, coin // 2, coin // 2, coin / 390.0)
    coin_layer.alpha_composite(skull_layer)

    # Selo verde de "ativo" no canto inferior direito.
    badge_center = int(size * 0.795)
    badge_radius = int(size * 0.085)
    cd_badge = ImageDraw.Draw(canvas)
    cd_badge.ellipse(
        (
            badge_center - badge_radius - int(size * 0.012),
            badge_center - badge_radius - int(size * 0.012),
            badge_center + badge_radius + int(size * 0.012),
            badge_center + badge_radius + int(size * 0.012),
        ),
        fill=(10, 17, 32, 255),
    )
    cd_badge.ellipse(
        (
            badge_center - badge_radius,
            badge_center - badge_radius,
            badge_center + badge_radius,
            badge_center + badge_radius,
        ),
        fill=GREEN + (255,),
    )
    check = int(badge_radius * 0.45)
    cd_badge.line(
        (
            badge_center - check,
            badge_center,
            badge_center - int(check * 0.15),
            badge_center + int(check * 0.65),
            badge_center + check,
            badge_center - int(check * 0.55),
        ),
        fill=(6, 45, 32, 255),
        width=max(4, int(size * 0.018)),
        joint="curve",
    )

    canvas.alpha_composite(coin_layer, (center - coin // 2, center - coin // 2))
    sparkle_draw = ImageDraw.Draw(canvas)
    _sparkle(sparkle_draw, int(size * 0.82), int(size * 0.17), int(size * 0.045), (255, 241, 190, 235))
    _sparkle(sparkle_draw, int(size * 0.16), int(size * 0.73), int(size * 0.028), (255, 241, 190, 190))
    return canvas


def _gradient_text(
    base: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> None:
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255)
    gradient = _linear_gradient(base.size, top, bottom, angle=90)
    base.paste(gradient, (0, 0), mask)


def make_banner(width: int = 1280, height: int = 360) -> Image.Image:
    banner = _linear_gradient((width, height), NAVY_TOP, (24, 42, 72), angle=110)
    draw = ImageDraw.Draw(banner)

    # Halo e linhas discretas.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-180, -300, 560, 440), fill=(245, 196, 81, 26))
    od.ellipse((930, 40, 1500, 610), fill=(52, 211, 153, 16))
    banner.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(40)))

    for x in range(0, width, 48):
        draw.line((x, 0, x, height), fill=(28, 45, 76, 255), width=1)

    logo = make_logo(250)
    banner.alpha_composite(logo, (54, (height - 250) // 2))

    title_font = _font(88, bold=True)
    subtitle_font = _font(30, bold=False)
    tag_font = _font(19, bold=False)
    _gradient_text(banner, (348, 70), "PIRATE FARM", title_font, (255, 239, 188), (214, 154, 45))
    draw = ImageDraw.Draw(banner)
    draw.text((352, 184), "Farm AFK do token Pirate Shop Access", font=subtitle_font, fill=TEXT)
    draw.text(
        (352, 238),
        "Fortnite  ·  Python  ·  OpenCV  ·  Tkinter  ·  PT-BR",
        font=tag_font,
        fill=MUTED,
    )
    draw.line((352, 284, 1200, 284), fill=(245, 196, 81, 90), width=2)
    draw.text((352, 298), "AFK inteligente, detecção local e foco rápido", font=tag_font, fill=(245, 196, 81))
    return banner


def make_social_preview(width: int = 1280, height: int = 640) -> Image.Image:
    canvas = _linear_gradient((width, height), NAVY_TOP, (16, 29, 52), angle=120)
    draw = ImageDraw.Draw(canvas)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-260, -360, 620, 520), fill=(245, 196, 81, 30))
    od.ellipse((860, 180, 1600, 920), fill=(52, 211, 153, 18))
    canvas.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(60)))

    logo = make_logo(300)
    canvas.alpha_composite(logo, (90, 170))

    title_font = _font(94, bold=True)
    subtitle_font = _font(31, bold=False)
    tag_font = _font(20, bold=False)
    _gradient_text(canvas, (450, 190), "PIRATE FARM", title_font, (255, 239, 188), (214, 154, 45))
    draw = ImageDraw.Draw(canvas)
    draw.text((456, 308), "Farm AFK do token Pirate Shop Access", font=subtitle_font, fill=TEXT)
    draw.text((456, 360), "Fortnite · Python · OpenCV · Tkinter · PT-BR", font=tag_font, fill=MUTED)
    draw.line((456, 410, 1188, 410), fill=(245, 196, 81, 100), width=2)
    draw.text((456, 428), "github.com/droxz/fortnite-pirate-farm", font=tag_font, fill=(245, 196, 81))
    _sparkle(draw, 1110, 140, 28, (255, 241, 190, 210))
    _sparkle(draw, 1190, 520, 18, (255, 241, 190, 150))
    return canvas


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    logo = make_logo(512)
    logo.save(ASSETS / "logo.png")
    logo.resize((256, 256), Image.LANCZOS).save(ASSETS / "logo_256.png")
    logo.resize((64, 64), Image.LANCZOS).save(ASSETS / "logo_64.png")
    make_banner().save(DOCS / "banner.png")
    make_social_preview().save(DOCS / "social_preview.png")
    print("Logo: assets/logo.png")
    print("Banner: docs/banner.png")
    print("Social preview: docs/social_preview.png")


if __name__ == "__main__":
    main()
