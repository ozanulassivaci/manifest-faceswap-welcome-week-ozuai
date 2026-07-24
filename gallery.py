"""
Welcome Week Standı - Kiosk Arayüzü
====================================
- Webcam canlı görüntüsü ve karakter seçim galerisi TEK bir pencerede
  (KioskWindow), aralarında sürüklenebilir/katlanabilir bir ayırıcı ile.
- Webcam SOLDA, galeri SAĞDA sabit bir şerit olarak başlıyor.
- Normal bir pencere olarak açılır (başlık çubuğu var, taşınabilir/yeniden
  boyutlandırılabilir, tam ekran DEĞİL) - ekranın ortasında, makul bir
  boyutla (WINDOW_WIDTH x WINDOW_HEIGHT) başlar.
- Deep-Live-Cam'in kendi ayar penceresi (Mouth Mask, Face Enhancer vb.)
  arka planda, sol üst köşede küçük bir pencere olarak açık duruyor,
  gerektiğinde öne getirilebilir (Alt+Tab).
- Uygulama açılır açılmaz kamera otomatik başlıyor ve galerideki İLK
  fotoğrafı varsayılan yüz olarak kullanıyor - stand boşken bile canlı
  görüntü akıyor.
- Çıkış için: pencereyi kapat (X) veya Ctrl+Shift+Q

KLASÖR YAPISI (bu dosyayı Deep-Live-Cam'in ana klasörüne koy):
    Deep-Live-Cam/
    ├── gallery.py              <- bu dosya
    ├── gallery_images/         <- karakterlerin/ünlülerin fotoğrafları
    ├── club_logo.png           <- kulüp logon
    └── modules/                <- Deep-Live-Cam'in kendi kodu (dokunma)

ÇALIŞTIRMA:
    python gallery.py
"""

import sys
import os
import queue
from pathlib import Path

import cv2

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QScrollArea, QFrame, QSplitter, QPushButton
)
from PySide6.QtGui import QPixmap, QFont, QCursor, QShortcut, QKeySequence
from PySide6.QtCore import Qt, Signal, QObject

try:
    import pyvirtualcam
    VIRTUALCAM_AVAILABLE = True
except ImportError:
    VIRTUALCAM_AVAILABLE = False
    print("[VirtualCam] pyvirtualcam kurulu değil, sanal kamera devre dışı. "
          "Kurmak için: pip install pyvirtualcam")

# ── Deep-Live-Cam'in kendi modülleri ──────────────────────────────────
import modules.globals
import modules.core as core
import modules.ui as dlc_ui
from modules.core import decode_execution_providers, suggest_execution_threads
from modules.face_analyser import get_face_analyser
from modules.processors.frame.face_swapper import get_face_swapper
from modules.ui import (
    WebcamPreviewWindow, get_available_cameras,
    fit_image_to_size, _bgr_to_qpixmap,
)


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


# ----------------------------------------------------------------------
# AYARLAR
# ----------------------------------------------------------------------
GALLERY_FOLDER = "gallery_images"
LOGO_PATH = "club_logo.png"
WINDOW_TITLE = "OZÜ AI Kulübü - Kendini Dönüştür!"
THUMBNAIL_SIZE = 200
GRID_COLUMNS = 2                       # panel dar olduğu için 2 sütun
PANEL_WIDTH = 420                      # sağdaki galeri panelinin genişliği
WINDOW_WIDTH = 1280                    # normal pencere modundaki başlangıç genişliği
WINDOW_HEIGHT = 800                    # normal pencere modundaki başlangıç yüksekliği
CAMERA_INDEX = 0
EXECUTION_PROVIDER = "cuda"            # RTX 4070 için

BG_COLOR = "#0d0d12"
CARD_COLOR = "#1a1a24"
CARD_HOVER = "#2a2a3a"
ACCENT_COLOR = "#3d7fff"
TEXT_COLOR = "#ffffff"


class SelectionSignal(QObject):
    photo_selected = Signal(str)


class PhotoCard(QFrame):
    def __init__(self, image_path: str, signal: SelectionSignal, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.signal = signal
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE + 40)
        self._selected = False
        self._build_ui()

    def _build_ui(self):
        self._apply_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        img_label = QLabel()
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                THUMBNAIL_SIZE - 16, THUMBNAIL_SIZE - 16,
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(THUMBNAIL_SIZE - 16, THUMBNAIL_SIZE - 16)
        img_label.setStyleSheet("border-radius: 10px;")
        layout.addWidget(img_label)

        name = Path(self.image_path).stem.replace("_", " ").title()
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12px; border: none;")
        layout.addWidget(name_label)

    def _apply_style(self):
        border = f"3px solid {ACCENT_COLOR}" if self._selected else "3px solid transparent"
        self.setStyleSheet(f"""
            PhotoCard {{
                background-color: {CARD_COLOR};
                border-radius: 14px;
                border: {border};
            }}
            PhotoCard:hover {{
                background-color: {CARD_HOVER};
            }}
        """)

    def set_selected(self, value: bool):
        self._selected = value
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.signal.photo_selected.emit(self.image_path)
        super().mousePressEvent(event)


class GalleryPanel(QWidget):
    """Karakter seçim paneli - KioskWindow içine gömülen bir şerit widget'ı."""

    def __init__(self):
        super().__init__()
        self.signal = SelectionSignal()
        self.signal.photo_selected.connect(self.on_photo_selected)

        self.cards: list[PhotoCard] = []

        self._build_ui()
        self.setStyleSheet(f"background-color: {BG_COLOR};")

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title = QLabel("Kendini\nDönüştür!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {TEXT_COLOR}; padding: 20px;")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        self.status_label = QLabel("Bir fotoğraf seç →")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {ACCENT_COLOR}; font-size: 13px; padding-bottom: 10px;")
        main_layout.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(16)
        grid_layout.setContentsMargins(16, 10, 16, 10)
        grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        image_paths = self._load_gallery_images()
        if not image_paths:
            empty_label = QLabel(
                f"'{GALLERY_FOLDER}' klasöründe\nfotoğraf bulunamadı."
            )
            empty_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
            empty_label.setAlignment(Qt.AlignCenter)
            grid_layout.addWidget(empty_label, 0, 0)
        else:
            for i, path in enumerate(image_paths):
                row, col = divmod(i, GRID_COLUMNS)
                card = PhotoCard(path, self.signal)
                self.cards.append(card)
                grid_layout.addWidget(card, row, col)

        scroll.setWidget(grid_widget)
        main_layout.addWidget(scroll, stretch=1)

        footer = QWidget()
        footer.setFixedHeight(90)
        footer.setStyleSheet(f"background-color: {CARD_COLOR};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setAlignment(Qt.AlignCenter)

        if os.path.exists(LOGO_PATH):
            logo_label = QLabel()
            logo_pixmap = QPixmap(LOGO_PATH).scaledToHeight(60, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            footer_layout.addWidget(logo_label)
        else:
            placeholder = QLabel("[Kulüp Logosu]")
            placeholder.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 11px;")
            footer_layout.addWidget(placeholder)

        main_layout.addWidget(footer)

    def _load_gallery_images(self):
        folder = Path(GALLERY_FOLDER)
        if not folder.exists():
            return []
        extensions = {".jpg", ".jpeg", ".png", ".webp"}
        return sorted(
            str(p) for p in folder.iterdir()
            if p.suffix.lower() in extensions
        )

    def select_default(self):
        """Açılışta ilk fotoğrafı varsayılan olarak işaretle."""
        if self.cards:
            modules.globals.source_path = self.cards[0].image_path
            self.cards[0].set_selected(True)
            self.status_label.setText(f"Aktif: {Path(self.cards[0].image_path).stem}")

    def on_photo_selected(self, image_path: str):
        print(f"[Galeri] Seçilen fotoğraf: {image_path}")
        for card in self.cards:
            card.set_selected(card.image_path == image_path)
        # Webcam işleme thread'i bu değişikliği otomatik algılayıp
        # kamerayı yeniden başlatmadan yeni yüzü yükleyecek.
        modules.globals.source_path = image_path
        self.status_label.setText(f"Aktif: {Path(image_path).stem}")


class KioskWindow(QMainWindow):
    """Kamera görüntüsü ve galeri panelini tek normal pencerede barındırır."""

    def __init__(self, webcam_widget: QWidget, gallery_widget: GalleryPanel, screen_geo):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._webcam_widget = webcam_widget
        self._gallery_widget = gallery_widget

        # Normal pencere: başlık çubuğu + taşınabilir/yeniden boyutlandırılabilir,
        # ekranın ortasında makul bir boyutla açılır.
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.move(
            screen_geo.x() + (screen_geo.width() - WINDOW_WIDTH) // 2,
            screen_geo.y() + (screen_geo.height() - WINDOW_HEIGHT) // 2,
        )

        # ── Sürüklenebilir ayırıcı: kamera solda, galeri sağda ────────────
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(6)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {CARD_COLOR}; }}
            QSplitter::handle:hover {{ background-color: {ACCENT_COLOR}; }}
        """)
        self._splitter.addWidget(webcam_widget)
        self._splitter.addWidget(gallery_widget)
        self._splitter.setStretchFactor(0, 1)   # pencere büyüyünce kamera genişler
        self._splitter.setStretchFactor(1, 0)   # galeri sürüklenen genişliğini korur
        self._splitter.setCollapsible(0, False)  # kamera tarafı asla sıfıra inmesin
        self._splitter.setCollapsible(1, True)   # galeri sürükleyerek de kapatılabilir

        self._expanded_sizes = [WINDOW_WIDTH - PANEL_WIDTH, PANEL_WIDTH]
        self._splitter.setSizes(self._expanded_sizes)

        self.setCentralWidget(self._splitter)

        # ── Paneli aç/kapa butonu: splitter'ın dışında, hep görünür kalsın ─
        self._toggle_btn = QPushButton("›", self)
        self._toggle_btn.setFixedSize(40, 56)
        self._toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_btn.setToolTip("Paneli kapat/aç")
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_COLOR};
                color: {TEXT_COLOR};
                border: 2px solid {ACCENT_COLOR};
                border-radius: 8px;
                font-size: 20px;
            }}
            QPushButton:hover {{ background-color: {CARD_HOVER}; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_panel)
        self._position_toggle_button()

        QShortcut(QKeySequence("Ctrl+Shift+Q"), self, activated=self._exit_app)

    def _position_toggle_button(self):
        self._toggle_btn.move(self.width() - self._toggle_btn.width() - 16, 16)
        self._toggle_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toggle_button()

    def _toggle_panel(self):
        if self._gallery_widget.isVisible():
            self._expanded_sizes = self._splitter.sizes()
            self._gallery_widget.hide()
            self._toggle_btn.setText("‹")
        else:
            self._gallery_widget.show()
            self._splitter.setSizes(self._expanded_sizes)
            self._toggle_btn.setText("›")
        self._position_toggle_button()

    def _exit_app(self):
        QApplication.instance().quit()

    def closeEvent(self, event):
        self._exit_app()
        event.accept()


def main():
    app = QApplication(sys.argv)
    screen_geo = app.primaryScreen().geometry()

    # ── 0) KRİTİK: CUDA hızlandırmayı elle etkinleştir ───────────────────
    # Normalde bu, "python run.py --execution-provider cuda" çalıştırılınca
    # core.parse_args() tarafından ayarlanıyor. Biz run.py'ı hiç
    # çalıştırmadığımız için bunu burada elle yapmamız gerekiyor - yoksa
    # her şey sessizce CPU'ya düşüyor (1-2 fps'in sebebi buydu).
    modules.globals.execution_providers = decode_execution_providers([EXECUTION_PROVIDER])
    modules.globals.execution_threads = suggest_execution_threads()
    if not modules.globals.frame_processors:
        modules.globals.frame_processors = ["face_swapper"]

    # ── 1) Deep-Live-Cam'in kendi ayar arayüzünü arka planda başlat ──────
    settings_window = dlc_ui.init(core.start, core.destroy, "en")
    settings_window._main.show()
    settings_window._main.setGeometry(20, 20, 640, 820)

    # Kamera zaten aşağıda KioskWindow içine gömülü olarak açılacak.
    # Ayar panelindeki "Live" düğmesi tıklanırsa modules/ui.py kendi
    # başına AYRI bir "Live Preview" penceresi açıyor (_open_webcam_preview) -
    # bunu önlemek için düğmeyi burada devre dışı bırakıyoruz.
    settings_window._main.btn_live.setEnabled(False)
    settings_window._main.btn_live.setToolTip(
        "Kamera zaten ana pencerede açık - kiosk modunda devre dışı."
    )

    # ── 2) Modelleri önceden yükle (açılışta bir kereye mahsus) ──────────
    get_face_analyser()
    get_face_swapper()

    # ── 3) Kamerayı hemen başlat (henüz gömülü, top-level pencere değil) ──
    camera_indices, camera_names = get_available_cameras()
    if not camera_indices:
        print("[HATA] Hiçbir kamera algılanamadı.")
        sys.exit(1)
    camera_index = CAMERA_INDEX if CAMERA_INDEX in camera_indices else camera_indices[0]

    webcam_widget = VirtualCamWebcamWindow(camera_index)

    # ── 4) Galeri panelini oluştur (henüz gömülü, top-level pencere değil) ─
    gallery = GalleryPanel()
    gallery.select_default()  # ilk fotoğrafı varsayılan yüz yap

    # ── 5) İkisini tek pencerede birleştir, normal pencere olarak aç ──────
    kiosk = KioskWindow(webcam_widget, gallery, screen_geo)
    kiosk.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()