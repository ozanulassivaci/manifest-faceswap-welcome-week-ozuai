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
- Galeride varsayılan olarak "Sueda" fotoğrafı seçili gelir (bulunamazsa
  ilk fotoğraf). Kamera OTOMATİK başlamaz: sol tarafta "Başlat" düğmesine
  basılana kadar bir yer tutucu görünür - böylece kamera thread'i ilk
  kareyi işlemeye başladığında source_path zaten dolu olur.
- Çıkış için: pencereyi kapat (X) veya Ctrl+Shift+Q

KLASÖR YAPISI (bu dosyayı Deep-Live-Cam'in ana klasörüne koy):
    Deep-Live-Cam/
    ├── gallery.py              <- bu dosya: sadece başlatma/orkestrasyon
    ├── camera.py               <- kamera başlatma, frame okuma, kapatma
    ├── faceswap.py             <- Deep-Live-Cam motoruyla entegrasyon
    ├── ui.py                   <- PySide6 arayüz bileşenleri
    ├── gallery_images/         <- karakterlerin/ünlülerin fotoğrafları
    ├── club_logo.png           <- kulüp logon
    └── modules/                <- Deep-Live-Cam'in kendi kodu (dokunma)

ÇALIŞTIRMA:
    python gallery.py
"""

import sys

from PySide6.QtWidgets import QApplication

import faceswap
from ui import GalleryPanel, KioskWindow


def main():
    app = QApplication(sys.argv)
    screen_geo = app.primaryScreen().geometry()

    # 0) KRİTİK: CUDA hızlandırmayı elle etkinleştir (bkz. faceswap.py).
    faceswap.configure_execution_provider()

    # 1) Deep-Live-Cam'in kendi ayar arayüzünü arka planda başlat.
    settings_window, resolve_camera_index = faceswap.init_settings_window()

    # 2) Modelleri önceden yükle (açılışta bir kereye mahsus).
    faceswap.preload_models()

    # 3) Kamera indeksi ayar panelindeki seçime göre "Başlat" tıklamasında
    #    çözülecek (resolve_camera_index); burada sadece hiç kamera var mı
    #    kontrol ediyoruz.
    if not faceswap.has_camera(settings_window):
        print("[HATA] Hiçbir kamera algılanamadı.")
        sys.exit(1)

    # 4) Galeri panelini oluştur, varsayılan yüzü (Sueda) ŞİMDİ seç.
    # Kamera işleme thread'i başlamadan ÖNCE modules.globals.source_path
    # dolu olmalı; aksi halde ilk karede bir yüz algılanırsa source_image=None
    # ile swap denenip thread sessizce çöküyor ve bir daha görüntü gelmiyor.
    gallery = GalleryPanel()
    gallery.select_default()

    # 5) İkisini tek pencerede birleştir, normal pencere olarak aç.
    # Kamera burada değil, kullanıcı "Başlat" düğmesine basınca oluşturulur.
    kiosk = KioskWindow(resolve_camera_index, gallery, screen_geo)
    kiosk.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
