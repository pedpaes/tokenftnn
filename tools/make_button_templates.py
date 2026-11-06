"""Cria e valida templates dos botoes JOGAR e CONTINUAR JOGANDO."""
import os
import cv2
import numpy as np

SHOTS = r"C:\Users\nvd\Documents\Projeto Padrão\screenshots"
ASSETS = r"C:\Users\nvd\Documents\Projeto Padrão\fortnite_pirate_farm\assets"


def imread_unicode(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path, img):
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    assert ok, path
    buf.tofile(path)


def match(img, templ, thresh=0.6):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tg = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    best = (0.0, None, None)
    for scale in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
        tw = int(round(tg.shape[1] * scale))
        th = int(round(tg.shape[0] * scale))
        if tw >= gray.shape[1] or th >= gray.shape[0] or tw < 40:
            continue
        t = cv2.resize(tg, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if maxv > best[0]:
            best = (float(maxv), maxloc, (tw, th))
    return best


# Recorta o botao JOGAR do lobby real (verde, com texto)
lobby = imread_unicode(os.path.join(SHOTS, "game_after_resume.png"))
play = lobby[900:978, 90:440].copy()
imwrite_unicode(os.path.join(ASSETS, "play_button.png"), play)
print("play_button", play.shape)

# Recorta o botao CONTINUAR JOGANDO da tela de suspensao
susp = imread_unicode(os.path.join(SHOTS, "game_focused.png"))
cont = susp[468:524, 778:1142].copy()
imwrite_unicode(os.path.join(ASSETS, "suspend_button.png"), cont)
print("suspend_button", cont.shape)

imgs = {
    "POS_lobby": lobby,
    "POS_suspensao": susp,
    "NEG_desktop": imread_unicode(os.path.join(SHOTS, "fortnite_now.png")),
}
for name in ["token_frvr.jpg", "token_frvr2.jpg", "token_biglead.jpg", "banner_timesaver.jpg"]:
    imgs["NEG_ref_" + name] = imread_unicode(os.path.join(SHOTS, "ref", name))

for name, img in imgs.items():
    if img is None:
        print(name, "nao lido")
        continue
    s1 = match(img, play)
    s2 = match(img, cont)
    print(f"{name:32s} play={s1[0]:.3f}@{s1[1]} {s1[2]}  continue={s2[0]:.3f}@{s2[1]} {s2[2]}")
