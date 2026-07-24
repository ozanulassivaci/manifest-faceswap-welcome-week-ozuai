"""
Kamera yakalama + sanal kamera (OBS Virtual Camera) entegrasyonu.

Deep-Live-Cam'in kendi `WebcamPreviewWindow`'unu (modules/ui.py) genişletir:
kamerayı başlatma, işlenmiş kareleri okuma, ekranda gösterme ve aynı kareyi
bir sanal kameraya gönderme sorumluluğu burada.
"""

import queue

import cv2

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

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

# Filtresiz (ham) önizlemenin köşedeki kutusu için boyut/kenar payı
# 4:3 oranı PREVIEW_DEFAULT_WIDTH/HEIGHT (640x480, modules/ui.py) ile aynı -
# böylece letterbox/boşluk oluşmadan tam oturuyor.
RAW_PREVIEW_WIDTH = 320
RAW_PREVIEW_HEIGHT = 240
RAW_PREVIEW_MARGIN = 16


class VirtualCamWebcamWindow(WebcamPreviewWindow):
    """
    WebcamPreviewWindow'u genişletiyor: ekranda gösterdiği her işlenmiş
    kareyi AYNI ZAMANDA bir sanal kameraya (OBS Virtual Camera üzerinden)
    gönderiyor. Bu sayede Zoom/Teams/Meet gibi uygulamalarda "Kamera"
    listesinde bu görüntü seçilebilir hale geliyor.
    """

    def __init__(self, camera_index: int):
        self._vcam = None
        self._raw_frame = None
        super().__init__(camera_index)
        if ENABLE_VIRTUAL_CAM and VIRTUALCAM_AVAILABLE:
            self._init_virtual_cam()
        if getattr(self._cap, "is_running", False):
            self._tap_raw_frames()
            self._build_raw_preview()

    def _tap_raw_frames(self):
        """
        Deep-Live-Cam'in kendi _CaptureWorker'ı (modules/ui.py) her karede
        self._cap.read() çağırıp sonucu doğrudan işleme kuyruğuna koyuyor -
        ham kareyi ayrıca dışarı vermiyor. modules/ui.py'a dokunmadan, aynı
        tek okuma noktasına bir "gözlemci" ekliyoruz: VideoCapturer
        INSTANCE'ının (sınıfının değil) read() metodunu, davranışını hiç
        değiştirmeden (aynı (ret, frame) çiftini aynen döndürerek) sarmalıyoruz.
        Ekstra okuma/thread YOK, yarış durumu yok - tek okumaya tek gözlemci.

        ÖNEMLİ: frame'i .copy() ile saklıyoruz. _ProcessingWorker aynı array
        referansını mirror/swap/enhancer adımlarında yerinde (in-place)
        değiştirebiliyor; kopyalamadan sadece referans saklarsak "ham" önizleme
        de o değişiklikleri görüp filtre uygulanmış gibi titreşmeye başlıyordu.
        """
        original_read = self._cap.read

        def _read_and_tap():
            ret, frame = original_read()
            if ret:
                self._raw_frame = frame.copy()
            return ret, frame

        self._cap.read = _read_and_tap

    def _build_raw_preview(self):
        """Sağ altta, filtreli görüntünün ÜSTÜNDE duran küçük ham kamera kutusu."""
        self._raw_preview_label = QLabel(self)
        self._raw_preview_label.setFixedSize(RAW_PREVIEW_WIDTH, RAW_PREVIEW_HEIGHT)
        self._raw_preview_label.setAlignment(Qt.AlignCenter)
        self._raw_preview_label.setStyleSheet(
            "background-color: #000000; border: 2px solid #3d7fff; border-radius: 8px;"
        )

        self._raw_preview_caption = QLabel("Orijinal", self)
        self._raw_preview_caption.setStyleSheet(
            "color: #ffffff; font-size: 11px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 160); padding: 2px 8px; border-radius: 6px;"
        )
        self._raw_preview_caption.adjustSize()

        self._position_raw_preview()
        self._raw_preview_label.raise_()
        self._raw_preview_caption.raise_()

    def _position_raw_preview(self):
        if not hasattr(self, "_raw_preview_label"):
            return
        x = self.width() - RAW_PREVIEW_WIDTH - RAW_PREVIEW_MARGIN
        y = self.height() - RAW_PREVIEW_HEIGHT - RAW_PREVIEW_MARGIN
        self._raw_preview_label.move(x, y)
        self._raw_preview_caption.move(x + 8, y - self._raw_preview_caption.height() - 4)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_raw_preview()

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

        # ── Filtresiz ham görüntüyü köşedeki küçük kutuda göster ─────────
        if self._raw_frame is not None and hasattr(self, "_raw_preview_label"):
            raw_display = fit_image_to_size(
                self._raw_frame,
                self._raw_preview_label.width(),
                self._raw_preview_label.height(),
            )
            self._raw_preview_label.setPixmap(_bgr_to_qpixmap(raw_display))

    def closeEvent(self, event) -> None:
        if self._vcam is not None:
            try:
                self._vcam.close()
            except Exception:
                pass
        super().closeEvent(event)
