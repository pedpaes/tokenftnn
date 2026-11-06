"""Compara abordagens de deteccao: template cinza, mascara do F e ORB."""
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


def white_mask(bgr, s_max=80, v_min=185):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, v_min), (180, s_max, 255))


def gold_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (5, 80, 80), (42, 255, 255))


def make_f_template():
    img = imread_unicode(os.path.join(REF, "token_frvr2.jpg"))
    crop = img[170:450, 450:730].copy()
    wm = white_mask(crop)
    wm = cv2.morphologyEx(wm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(wm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    best = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if area < 300:
            continue
        # F fica perto do centro
        cx, cy = x + w / 2, y + h / 2
        if abs(cx - 140) < 60 and abs(cy - 140) < 80 and h > w:
            best = (x, y, w, h, area)
            break
    print("F bbox:", best)
    if not best:
        raise SystemExit("F nao encontrado")
    x, y, w, h, _ = best
    pad = 4
    f = crop[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
    fmask = wm[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
    imwrite_unicode(os.path.join(ASSETS, "f_template.png"), f)
    imwrite_unicode(os.path.join(ASSETS, "f_template_mask.png"), fmask)
    return f, fmask


def detect_gray(img, templ, sizes):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    best = (0.0, None, None)
    for tw in sizes:
        th = int(round(tg.shape[0] * tw / tg.shape[1]))
        if th < 20 or tw >= gray.shape[1] or th >= gray.shape[0]:
            continue
        t = cv2.resize(tg, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if maxv > best[0]:
            best = (maxv, maxloc, (tw, th))
    return best


def detect_f(img, ftempl, fmask, sizes, thresh=0.5):
    wm = white_mask(img)
    ft = cv2.cvtColor(ftempl, cv2.COLOR_BGR2GRAY)
    hits = []
    for tw in sizes:
        th = int(round(ft.shape[0] * tw / ft.shape[1]))
        if th < 12 or tw >= wm.shape[1] or th >= wm.shape[0]:
            continue
        t = cv2.resize(ft, (tw, th), interpolation=cv2.INTER_NEAREST)
        m = cv2.resize(fmask, (tw, th), interpolation=cv2.INTER_NEAREST)
        # usa apenas pixels do F como mascara
        res = cv2.matchTemplate(wm, t, cv2.TM_CCORR_NORMED, mask=m)
        ys, xs = np.where(res >= thresh)
        for y, x in zip(ys, xs):
            hits.append((float(res[y, x]), x, y, tw, th))
    hits.sort(reverse=True)
    return hits[:10]


def gold_ring_score(img, cx, cy, fh):
    """Verifica se ha um disco dourado ao redor do F."""
    h, w = img.shape[:2]
    R = int(fh * 2.3)
    x0, y0 = max(0, cx - R), max(0, cy - R)
    x1, y1 = min(w, cx + R), min(h, cy + R)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return 0.0, 0.0
    gm = gold_mask(crop)
    # anel externo
    yy, xx = np.ogrid[:crop.shape[0], :crop.shape[1]]
    ccy, ccx = cy - y0, cx - x0
    dist = np.sqrt((xx - ccx) ** 2 + (yy - ccy) ** 2)
    ann = (dist > R * 0.55) & (dist < R * 0.95)
    ring = gm[ann] > 0
    gold_ratio = float(ring.mean()) if ring.size else 0.0
    # centro deve ser dourado/laranja atras do F
    inner = dist < R * 0.5
    inner_gold = float((gm[inner] > 0).mean()) if inner.size else 0.0
    return gold_ratio, inner_gold


def orb_test(img, templ):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1000)
    k1, d1 = orb.detectAndCompute(tg, None)
    k2, d2 = orb.detectAndCompute(gray, None)
    if d1 is None or d2 is None:
        return 0, 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(d1, d2)
    good = [m for m in matches if m.distance < 50]
    return len(k1 or []), len(good)


ftempl, fmask = make_f_template()
print("F template", ftempl.shape)

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
    print("gray template:", detect_gray(img, ftempl, [20, 30, 45, 65, 90, 130, 180, 240]))
    # O template cinza do F tambem e' testado, mas o ideal e' a moeda inteira.
    hits = detect_f(img, ftempl, fmask, [20, 30, 45, 65, 90, 130, 180, 240])
    for score, x, y, tw, th in hits[:5]:
        cx, cy = x + tw // 2, y + th // 2
        ring, inner = gold_ring_score(img, cx, cy, th)
        print(f"  F hit score={score:.3f} at=({x},{y}) size={tw}x{th} ring={ring:.2f} inner={inner:.2f}")
    kp, good = orb_test(img, ftempl)
    print(f"ORB keypoints={kp} goodmatches={good}")
