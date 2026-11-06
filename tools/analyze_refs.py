"""Analisa as imagens de referencia e imprime caixas candidatas da moeda."""
import os
import cv2
import numpy as np

REF = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots\ref"


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def gold_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (10, 80, 90), (40, 255, 255))


def white_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, 165), (180, 75, 255))


for name in ["token_frvr2.jpg", "token_biglead.jpg", "banner_timesaver.jpg", "token_frvr.jpg"]:
    path = os.path.join(REF, name)
    img = imread_unicode(path)
    if img is None:
        print(name, "NAO LIDO")
        continue
    h, w = img.shape[:2]
    print(f"\n=== {name} {w}x{h} ===")

    # Maior componente branca (o "F")
    wm = white_mask(img)
    wm = cv2.morphologyEx(wm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(wm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) < 100:
            continue
        print(f"  branco: x={x} y={y} w={cw} h={ch} area={cv2.contourArea(c):.0f}")

    # Maior componente dourada
    gm = gold_mask(img)
    gm = cv2.morphologyEx(gm, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    cnts, _ = cv2.findContours(gm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:3]
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        print(f"  dourado: x={x} y={y} w={cw} h={ch} area={cv2.contourArea(c):.0f}")
