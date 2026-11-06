"""Teste final do detector com regras combinadas e benchmark."""
import os
import time
import cv2
import numpy as np

REF = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots\ref"
ASSETS = r"C:\Users\nvd\Documents\Projeto Padrão\fortnite_pirate_farm\assets"
SHOTS = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots"


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def hsv(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)


def gold_ratio(bgr):
    m = cv2.inRange(hsv(bgr), (5, 70, 70), (42, 255, 255))
    return float((m > 0).mean())


def white_ratio_center(bgr):
    h, w = bgr.shape[:2]
    c = bgr[int(h * 0.28):int(h * 0.72), int(w * 0.28):int(w * 0.72)]
    m = cv2.inRange(hsv(c), (0, 0, 170), (180, 95, 255))
    return float((m > 0).mean())


def nms(hits, ratio=0.45):
    out = []
    for h in sorted(hits, key=lambda x: -x[0]):
        score, x, y, tw, th, kind = h
        cx, cy = x + tw / 2, y + th / 2
        if any(abs(cx - (o[1] + o[3] / 2)) < min(o[3], tw) * ratio and
               abs(cy - (o[2] + o[4] / 2)) < min(o[4], th) * ratio for o in out):
            continue
        out.append(h)
    return out


def load_templates():
    inner = imread_unicode(os.path.join(ASSETS, "coin_inner.png"))
    frame = imread_unicode(os.path.join(ASSETS, "coin_banner_frame_pt.png"))
    return {"inner": inner, "frame": frame}


def scan(img, templates, downscale=1280):
    h, w = img.shape[:2]
    scale = min(1.0, downscale / w)
    if scale < 1.0:
        small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    specs = {
        "inner": [60, 75, 95, 120, 150, 190, 240, 300, 380, 480, 600],
        "frame": [100, 125, 155, 195, 245, 305, 380],
    }
    hits = []
    for kind, templ in templates.items():
        tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        for tw in specs[kind]:
            tw2 = int(tw * scale)
            th2 = int(round(tg.shape[0] * tw2 / tg.shape[1]))
            if tw2 >= gray.shape[1] or th2 >= gray.shape[0] or tw2 < 35:
                continue
            t = cv2.resize(tg, (tw2, th2), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            thresh = 0.62 if kind == "inner" else 0.55
            if tw2 < 100:
                thresh = 0.55
            ys, xs = np.where(res >= thresh)
            for y, x in zip(ys, xs):
                y0, y1 = max(0, y - 2), min(res.shape[0], y + 3)
                x0, x1 = max(0, x - 2), min(res.shape[1], x + 3)
                if res[y, x] >= res[y0:y1, x0:x1].max() - 1e-6:
                    hits.append((float(res[y, x]), int(x), int(y), tw2, th2, kind))
    hits = nms(hits)
    out = []
    for score, x, y, tw, th, kind in hits:
        crop = small[y:y + th, x:x + tw]
        g = gold_ratio(crop)
        wh = white_ratio_center(crop)
        ok = (score >= (0.62 if kind == "inner" else 0.55) and g >= 0.45 and wh >= (0.08 if kind == "inner" else 0.05))
        if kind == "inner" and tw < 100:
            ok = (score >= 0.55 and g >= 0.55 and wh >= 0.12)
        if ok:
            out.append((score, x / scale, y / scale, tw / scale, th / scale, kind, g, wh))
    return out


templates = load_templates()
images = {
    "POS_banner_timesaver": imread_unicode(os.path.join(REF, "banner_timesaver.jpg")),
    "POS_token_frvr": imread_unicode(os.path.join(REF, "token_frvr.jpg")),
    "POS_token_frvr2": imread_unicode(os.path.join(REF, "token_frvr2.jpg")),
    "POS_token_biglead": imread_unicode(os.path.join(REF, "token_biglead.jpg")),
    "NEG_lobby_real": imread_unicode(os.path.join(SHOTS, "game_after_resume.png")),
    "NEG_suspensao": imread_unicode(os.path.join(SHOTS, "game_focused.png")),
    "NEG_desktop": imread_unicode(os.path.join(SHOTS, "fortnite_now.png")),
}

for name, img in images.items():
    if img is None:
        print(name, "nao lido")
        continue
    t0 = time.perf_counter()
    hits = scan(img, templates)
    dt = time.perf_counter() - t0
    print(f"\n=== {name} {img.shape[1]}x{img.shape[0]} ({dt*1000:.0f} ms) ===")
    if not hits:
        print("  nenhum match valido")
    for score, x, y, tw, th, kind, g, wh in hits[:6]:
        print(f"  {kind:5s} score={score:.3f} at=({x:.0f},{y:.0f}) size={tw:.0f}x{th:.0f} gold={g:.2f} white={wh:.2f}")
