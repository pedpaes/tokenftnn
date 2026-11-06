"""Testa os dois templates da moeda com validacao de cor e NMS."""
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


def hsv(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)


def gold_ratio(bgr):
    m = cv2.inRange(hsv(bgr), (5, 70, 70), (42, 255, 255))
    return float((m > 0).mean())


def white_ratio_center(bgr):
    h, w = bgr.shape[:2]
    c = bgr[int(h * 0.30):int(h * 0.70), int(w * 0.30):int(w * 0.70)]
    m = cv2.inRange(hsv(c), (0, 0, 175), (180, 85, 255))
    return float((m > 0).mean())


def make_templates():
    inner = imread_unicode(os.path.join(REF, "token_frvr2.jpg"))[170:450, 450:730].copy()
    # recorta o quadro dourado do banner (sem o texto)
    banner = imread_unicode(os.path.join(REF, "token_frvr.jpg"))[50:265, 425:655].copy()
    imwrite_unicode(os.path.join(ASSETS, "coin_inner.png"), inner)
    imwrite_unicode(os.path.join(ASSETS, "coin_banner_frame.png"), banner)
    return inner, banner


def nms(hits, min_dist_ratio=0.5):
    out = []
    for h in sorted(hits, key=lambda x: -x[0]):
        score, x, y, tw, th, kind = h
        cx, cy = x + tw / 2, y + th / 2
        if any(abs(cx - (o[1] + o[3] / 2)) < min(o[3], tw) * min_dist_ratio and
               abs(cy - (o[2] + o[4] / 2)) < min(o[4], th) * min_dist_ratio for o in out):
            continue
        out.append(h)
    return out


def scan(img, templates, sizes, thresh=0.45):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hits = []
    for kind, templ in templates.items():
        tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        for tw in sizes[kind]:
            th = int(round(tg.shape[0] * tw / tg.shape[1]))
            if tw >= gray.shape[1] or th >= gray.shape[0] or tw < 40 or th < 40:
                continue
            t = cv2.resize(tg, (tw, th), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            # pega maximos locais acima do limiar
            ys, xs = np.where(res >= thresh)
            for y, x in zip(ys, xs):
                # evita pegar toda a vizinhanca: so maximos locais
                y0, y1 = max(0, y - 2), min(res.shape[0], y + 3)
                x0, x1 = max(0, x - 2), min(res.shape[1], x + 3)
                if res[y, x] >= res[y0:y1, x0:x1].max() - 1e-6:
                    hits.append((float(res[y, x]), int(x), int(y), tw, th, kind))
    return nms(hits)


inner, banner = make_templates()
templates = {"inner": inner, "banner": banner}
sizes = {
    "inner": [70, 90, 110, 140, 180, 230, 290, 370, 470, 600],
    "banner": [100, 130, 160, 200, 250, 310],
}

images = {
    "token_frvr2": imread_unicode(os.path.join(REF, "token_frvr2.jpg")),
    "token_biglead": imread_unicode(os.path.join(REF, "token_biglead.jpg")),
    "banner_timesaver": imread_unicode(os.path.join(REF, "banner_timesaver.jpg")),
    "token_frvr": imread_unicode(os.path.join(REF, "token_frvr.jpg")),
    "NEG_desktop": imread_unicode(NEG),
}

for name, img in images.items():
    if img is None:
        print(name, "nao lido")
        continue
    print(f"\n=== {name} {img.shape[1]}x{img.shape[0]} ===")
    hits = scan(img, templates, sizes)
    for score, x, y, tw, th, kind in hits[:8]:
        crop = img[y:y + th, x:x + tw]
        g = gold_ratio(crop)
        w = white_ratio_center(crop)
        print(f"  {kind:6s} score={score:.3f} at=({x},{y}) {tw}x{th} gold={g:.2f} white={w:.2f}")
