from piratebot.config import ASSETS, load_config
from piratebot.vision import ScreenGrabber, TokenDetector, find_game_window, imwrite_u
import time

config = load_config()
window = find_game_window(config.game.window_title)
grabber = ScreenGrabber(window)
print("hwnd", window.hwnd, "client", window.width, window.height, "at", window.client_x, window.client_y)
print("foreground before:", grabber.is_foreground())
t0 = time.perf_counter()
frame = grabber.capture_background()
print("capture", frame.shape, f"{(time.perf_counter()-t0)*1000:.0f} ms")
print("mean", float(frame.mean()))
imwrite_u("logs/teste_bg_capture.png", frame)
detector = TokenDetector(ASSETS, config.detection)
print("token:", detector.detect(frame).found)
hit = detector.find_play_button(frame)
print("play:", hit)
print("foreground after:", grabber.is_foreground())
