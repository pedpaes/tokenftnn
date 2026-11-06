"""Testa o template da moeda interna nas imagens de referencia."""
import os
import cv2
import numpy as np

REF = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots\ref"
ASSETS = r"C:\Users\nvd\Documents\Projeto Padrão\fortnite_pirate_farm\assets"
NEG = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots\fortnite_now.png"


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path, img):
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    if ok:
        buf.tofile(path)


def make_template():
    img = imread_unicode(os.path.join(REF, "token_frvr2.jpg"))
    crop = img[170:450, 450:730].copy()
    # máscara circular suave
    mask = np.zeros(crop.shape[:2], np.uint8)
    cv2.circle(mask, (crop.shape[1] // 2, crop.shape[0] // 2), 132, 255, -1)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    imwrite_unicode(os.path.join(ASSETS, "coin_inner.png"), crop)
    imwrite_unicode(os.path.join(ASSETS, "coin_inner_mask.png"), mask)
    return crop, mask


def detect(img, templ, mask, sizes, thresh=0.5):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    best = (0.0, None, None)
    for tw in sizes:
        th = int(round(templ.shape[0] * tw / templ.shape[1]))
        if th < 20 or tw >= gray.shape[1] or th >= gray.shape[0]:
            continue
        t = cv2.resize(templ, (tw, th), interpolation=cv2.INTER_AREA)
        m = cv2.resize(mask, (tw, th), interpolation=cv2.INTER_NEAREST)
        res = cv2.matchTemplate(gray, cv2.cvtColor(t, cv2.COLOR_BGR2GRAY), cv2.TM_CCORR_NORMED, mask=m)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if maxv > best[0]:
            best = (maxv, maxloc, (tw, th))
    return best


templ, mask = make_template()
sizes = [50, 65, 80, 100, 125, 155, 190, 235, 290, 360, 450, 560, 700]
print("template", templ.shape)
for name in ["token_frvr2.jpg", "token_biglead.jpg", "banner_timesaver.jpg", "token_frvr.jpg"]:
    img = imread_unicode(os.path.join(REF, name))
    score, loc, size = detect(img, templ, mask, sizes)
    print(f"{name}: score={score:.3f} loc={loc} size={size}")

img = imread_unicode(NEG)
if img is not None:
    score, loc, size = detect(img, templ, mask, sizes)
    print(f"NEGATIVO desktop: score={score:.3f} loc={loc} size={size}")
else:
    print("negativo nao lido")
