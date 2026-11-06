"""Gera recortes candidatos para inspecao visual."""
import os
import cv2
import numpy as np

REF = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots\ref"
OUT = r"C:\Users\nvd\Documents\Projeto Padrão\fortnite_pirate_farm\assets\debug"
os.makedirs(OUT, exist_ok=True)

CROPS = [
    ("frvr2_coin", "token_frvr2.jpg", (330, 60, 860, 610)),
    ("frvr2_inner", "token_frvr2.jpg", (450, 170, 730, 450)),
    ("biglead_coin", "token_biglead.jpg", (320, 40, 750, 490)),
    ("biglead_inner", "token_biglead.jpg", (440, 150, 620, 340)),
    ("banner_coin", "banner_timesaver.jpg", (275, 75, 440, 240)),
    ("frvr_banner_coin", "token_frvr.jpg", (415, 40, 655, 275)),
    ("frvr_inner", "token_frvr.jpg", (455, 75, 610, 240)),
]


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path, img):
    ext = os.path.splitext(path)[1]
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(path)
    return ok


tiles = []
for name, src, (x1, y1, x2, y2) in CROPS:
    img = imread_unicode(os.path.join(REF, src))
    if img is None:
        print("falhou", src)
        continue
    crop = img[y1:y2, x1:x2].copy()
    imwrite_unicode(os.path.join(OUT, name + ".png"), crop)
    # montagem 220x220
    h, w = crop.shape[:2]
    s = min(220 / w, 220 / h)
    thumb = cv2.resize(crop, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    tile = np.full((260, 240, 3), 30, np.uint8)
    y0 = 30 + (220 - thumb.shape[0]) // 2
    x0 = 10 + (220 - thumb.shape[1]) // 2
    tile[y0:y0 + thumb.shape[0], x0:x0 + thumb.shape[1]] = thumb
    cv2.putText(tile, name, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    tiles.append(tile)

cols = 4
rows = (len(tiles) + cols - 1) // cols
while len(tiles) < rows * cols:
    tiles.append(np.full((260, 240, 3), 30, np.uint8))
montage = np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(rows)])
imwrite_unicode(os.path.join(OUT, "montage.png"), montage)
print("ok", montage.shape)
