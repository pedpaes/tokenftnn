"""Testa o template do quadro do banner (banner_timesaver)."""
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
    c = bgr[int(h * 0.28):int(h * 0.72), int(w * 0.28):int(w * 0.72)]
    m = cv2.inRange(hsv(c), (0, 0, 170), (180, 95, 255))
    return float((m > 0).mean())


def nms(hits, ratio=0.5):
    out = []
    for h in sorted(hits, key=lambda x: -x[0]):
        score, x, y, tw, th = h
        cx, cy = x + tw / 2, y + th / 2
        if any(abs(cx - (o[1] + o[3] / 2)) < min(o[3], tw) * ratio and
               abs(cy - (o[2] + o[4] / 2)) < min(o[4], th) * ratio for o in out):
            continue
        out.append(h)
    return out


def scan(img, templ, sizes, thresh=0.45):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    hits = []
    for tw in sizes:
        th = int(round(tg.shape[0] * tw / tg.shape[1]))
        if tw >= gray.shape[1] or th >= gray.shape[0] or tw < 40:
            continue
        t = cv2.resize(tg, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= thresh)
        for y, x in zip(ys, xs):
            y0, y1 = max(0, y - 2), min(res.shape[0], y + 3)
            x0, x1 = max(0, x - 2), min(res.shape[1], x + 3)
            if res[y, x] >= res[y0:y1, x0:x1].max() - 1e-6:
                hits.append((float(res[y, x]), int(x), int(y), tw, th))
    return nms(hits)


# recorte do quadro completo (sem texto)
src = imread_unicode(os.path.join(REF, "banner_timesaver.jpg"))
frame = src[88:238, 283:433].copy()
imwrite_unicode(os.path.join(ASSETS, "coin_banner_frame_pt.png"), frame)
print("template frame", frame.shape)

images = {
    "banner_timesaver": src,
    "token_frvr": imread_unicode(os.path.join(REF, "token_frvr.jpg")),
    "token_frvr2": imread_unicode(os.path.join(REF, "token_frvr2.jpg")),
    "token_biglead": imread_unicode(os.path.join(REF, "token_biglead.jpg")),
    "NEG_desktop": imread_unicode(NEG),
}
sizes = [90, 115, 145, 180, 225, 280, 350]

for name, img in images.items():
    if img is None:
        print(name, "nao lido")
        continue
    print(f"\n=== {name} ===")
    for score, x, y, tw, th in scan(img, frame, sizes)[:6]:
        crop = img[y:y + th, x:x + tw]
        print(f"  score={score:.3f} at=({x},{y}) {tw}x{th} gold={gold_ratio(crop):.2f} white={white_ratio_center(crop):.2f}")

# Teste do recorte verdadeiro do banner: qual o score no local correto?
print("\n=== score no local correto do banner_timesaver (283,88) ===")
gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
tg = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
res = cv2.matchTemplate(gray, tg, cv2.TM_CCOEFF_NORMED)
print("exato:", res[88, 283], "max:", res.max(), "maxloc:", np.unravel_index(res.argmax(), res.shape))
