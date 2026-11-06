"""Cria o template do botao CONTINUAR JOGANDO a partir da captura real."""
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


src = imread_unicode(os.path.join(SHOTS, "game_focused.png"))
print("origem", src.shape)
# botao CONTINUAR JOGANDO (inclui a borda arredondada e o texto)
crop = src[468:524, 778:1142].copy()
imwrite_unicode(os.path.join(ASSETS, "suspend_button.png"), crop)
print("salvo suspend_button.png", crop.shape)

# renomeia/copia o template do banner para o nome final
banner = imread_unicode(os.path.join(ASSETS, "coin_banner_frame_pt.png"))
imwrite_unicode(os.path.join(ASSETS, "coin_banner_frame.png"), banner)
print("salvo coin_banner_frame.png", banner.shape)

# template da aba JOGAR (para voltar ao lobby antes de iniciar)
lobby = imread_unicode(os.path.join(SHOTS, "game_after_resume.png"))
tab = lobby[40:92, 200:320].copy()
imwrite_unicode(os.path.join(ASSETS, "lobby_tab.png"), tab)
print("salvo lobby_tab.png", tab.shape)
