"""
PySide6 arayüz bileşenleri: karakter seçim kartları/paneli, kamera
başlangıç yer tutucusu ve ikisini barındıran tek kiosk penceresi.
"""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QScrollArea, QFrame, QSplitter, QPushButton,
)
from PySide6.QtGui import QPixmap, QFont, QCursor, QShortcut, QKeySequence
from PySide6.QtCore import Qt, Signal, QObject

import faceswap
from camera import VirtualCamWebcamWindow


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

    def select_default(self, preferred_name: str = "Sueda"):
        """Açılışta 'preferred_name' fotoğrafını (bulunamazsa ilkini) varsayılan yap."""
        if not self.cards:
            return
        card = next(
            (c for c in self.cards
             if Path(c.image_path).stem.lower() == preferred_name.lower()),
            self.cards[0],
        )
        faceswap.set_source_path(card.image_path)
        card.set_selected(True)
        self.status_label.setText(f"Aktif: {Path(card.image_path).stem}")

    def on_photo_selected(self, image_path: str):
        print(f"[Galeri] Seçilen fotoğraf: {image_path}")
        for card in self.cards:
            card.set_selected(card.image_path == image_path)
        # Webcam işleme thread'i bu değişikliği otomatik algılayıp
        # kamerayı yeniden başlatmadan yeni yüzü yükleyecek.
        faceswap.set_source_path(image_path)
        self.status_label.setText(f"Aktif: {Path(image_path).stem}")


class CameraPlaceholder(QWidget):
    """
    Kamera henüz başlatılmadan önce splitter'ın sol tarafında duran
    yer tutucu: ortada büyük bir "Başlat" düğmesi var, Live Preview
    düğmesinin kiosk modundaki karşılığı gibi düşünülebilir.
    """

    def __init__(self, on_start, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setFixedWidth(320)
        self.error_label.setStyleSheet(f"color: #ff6b6b; font-size: 13px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.start_btn = QPushButton("▶  Başlat")
        self.start_btn.setFixedSize(220, 70)
        self.start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: {TEXT_COLOR};
                border-radius: 14px;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2a6ae0; }}
        """)
        self.start_btn.clicked.connect(on_start)
        layout.addWidget(self.start_btn)

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()
        self.start_btn.setText("↻  Tekrar Dene")


class KioskWindow(QMainWindow):
    """Kamera görüntüsü ve galeri panelini tek normal pencerede barındırır."""

    def __init__(self, get_camera_index, gallery_widget: GalleryPanel, screen_geo):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._get_camera_index = get_camera_index  # () -> int, ayar panelindeki seçime bakar
        self._webcam_widget = None  # "Başlat" düğmesine basılana kadar oluşturulmaz
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
        self._camera_placeholder = CameraPlaceholder(self._start_camera)
        self._splitter.addWidget(self._camera_placeholder)
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

    def _start_camera(self):
        if self._webcam_widget is not None:
            return
        camera_index = self._get_camera_index()
        if camera_index is None:
            self._camera_placeholder.show_error("Hiçbir kamera algılanamadı.")
            return
        print(f"[Kiosk] Kamera başlatılıyor: index={camera_index} "
              f"(ayar panelindeki kamera seçimine göre)")
        widget = VirtualCamWebcamWindow(camera_index)

        # WebcamPreviewWindow, VideoCapturer.start() başarısız olursa
        # kendini sessizce kapatmaya çalışır (bkz. modules/ui.py); bu
        # yüzden burada da açıkça kontrol edip kullanıcıya görünür bir
        # hata gösteriyoruz, aksi halde ekranda hiçbir şey görünmüyordu.
        cap = getattr(widget, "_cap", None)
        if cap is None or not cap.is_running:
            print("[Kiosk] Kamera başlatılamadı (VideoCapturer.is_running=False). "
                  "Kamera başka bir uygulama tarafından kullanılıyor olabilir "
                  "ya da kamera indeksi hatalı olabilir.")
            self._camera_placeholder.show_error(
                "Kamera başlatılamadı.\n"
                "Başka bir uygulama kamerayı kullanıyor olabilir - kontrol edip tekrar deneyin."
            )
            return

        self._webcam_widget = widget
        old_placeholder = self._splitter.replaceWidget(0, widget)
        widget.show()
        if old_placeholder is not None:
            old_placeholder.deleteLater()
        print(f"[Kiosk] Kamera hazır: {cap.actual_width}x{cap.actual_height}"
              f"@{cap.actual_fps:.1f}fps")

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
