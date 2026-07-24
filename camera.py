"""
Kamera yakalama + sanal kamera (OBS Virtual Camera) entegrasyonu.

Deep-Live-Cam'in kendi `WebcamPreviewWindow`'unu (modules/ui.py) genişletir:
kamerayı başlatma, işlenmiş kareleri okuma, ekranda gösterme ve aynı kareyi
bir sanal kameraya gönderme sorumluluğu burada.
"""

import queue

import cv2

try:
    import pyvirtualcam
    VIRTUALCAM_AVAILABLE = True
except ImportError:
    VIRTUALCAM_AVAILABLE = False
    print("[VirtualCam] pyvirtualcam kurulu değil, sanal kamera devre dışı. "
          "Kurmak için: pip install pyvirtualcam")

from modules.ui import WebcamPreviewWindow, fit_image_to_size, _bgr_to_qpixmap


# Sanal kamerayı açık/kapalı yapmak için buradan kontrol et
ENABLE_VIRTUAL_CAM = True


class VirtualCamWebcamWindow(WebcamPreviewWindow):
    """
    WebcamPreviewWindow'u genişletiyor: ekranda gösterdiği her işlenmiş
    kareyi AYNI ZAMANDA bir sanal kameraya (OBS Virtual Camera üzerinden)
    gönderiyor. Bu sayede Zoom/Teams/Meet gibi uygulamalarda "Kamera"
    listesinde bu görüntü seçilebilir hale geliyor.
    """

    def __init__(self, camera_index: int):
        self._vcam = None
        super().__init__(camera_index)
        if ENABLE_VIRTUAL_CAM and VIRTUALCAM_AVAILABLE:
            self._init_virtual_cam()

    def _init_virtual_cam(self):
        try:
            width = self._cap.actual_width
            height = self._cap.actual_height
            fps = int(self._cap.actual_fps) or 30
            self._vcam = pyvirtualcam.Camera(width=width, height=height, fps=fps)
            print(f"[VirtualCam] Sanal kamera başlatıldı: {self._vcam.device} "
                  f"({width}x{height}@{fps}fps)")
        except Exception as exc:
            self._vcam = None
            print(f"[VirtualCam] Başlatılamadı: {exc}")
            print("[VirtualCam] OBS Studio kurulu ve OBS Virtual Camera "
                  "sürücüsü mevcut mu kontrol et.")

    def _tick(self) -> None:
        if self._stop_event.is_set():
            self.close()
            return
        try:
            bgr_frame = self._processed_queue.get_nowait()
        except queue.Empty:
            return

        # ── Sanal kameraya gönder (Zoom bu görüntüyü kullanacak) ────────
        if self._vcam is not None:
            try:
                rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                if (rgb_frame.shape[1] != self._vcam.width
                        or rgb_frame.shape[0] != self._vcam.height):
                    rgb_frame = cv2.resize(
                        rgb_frame, (self._vcam.width, self._vcam.height)
                    )
                self._vcam.send(rgb_frame)
                self._vcam.sleep_until_next_frame()
            except Exception as exc:
                print(f"[VirtualCam] Kare gönderilemedi: {exc}")

        # ── Ekrandaki önizlemeyi güncelle (mevcut davranış) ──────────────
        display_frame = fit_image_to_size(bgr_frame, self.width(), self.height())
        self._image_label.setPixmap(_bgr_to_qpixmap(display_frame))

    def closeEvent(self, event) -> None:
        if self._vcam is not None:
            try:
                self._vcam.close()
            except Exception:
                pass
        super().closeEvent(event)
