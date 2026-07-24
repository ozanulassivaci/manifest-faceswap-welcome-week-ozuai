"""
Deep-Live-Cam çekirdek motoruyla entegrasyon.

Yürütme sağlayıcısı (CUDA) ayarı, model ön-yükleme, motorun kendi ayar
penceresinin kurulması ve motorun global durumuna (aktif kaynak yüz vb.)
erişim buradan geçer - `modules/` klasörüne dokunan tek dosya bu.
"""

import modules.globals
import modules.core as core
import modules.ui as dlc_ui
from modules.core import decode_execution_providers, suggest_execution_threads
from modules.face_analyser import get_face_analyser
from modules.processors.frame.face_swapper import get_face_swapper


EXECUTION_PROVIDER = "cuda"            # RTX 4070 için


def configure_execution_provider(provider: str = EXECUTION_PROVIDER) -> None:
    """
    KRİTİK: Normalde bu, "python run.py --execution-provider cuda"
    çalıştırılınca core.parse_args() tarafından ayarlanıyor. run.py'ı hiç
    çalıştırmadığımız için bunu burada elle yapmamız gerekiyor - yoksa her
    şey sessizce CPU'ya düşüyor (1-2 fps'in sebebi buydu).
    """
    modules.globals.execution_providers = decode_execution_providers([provider])
    modules.globals.execution_threads = suggest_execution_threads()
    if not modules.globals.frame_processors:
        modules.globals.frame_processors = ["face_swapper"]


def preload_models() -> None:
    """Modelleri önceden yükle (açılışta bir kereye mahsus)."""
    get_face_analyser()
    get_face_swapper()


def init_settings_window():
    """
    Deep-Live-Cam'in kendi ayar arayüzünü (Mouth Mask, Face Enhancer vb.)
    arka planda başlatır. Kamera zaten kiosk penceresinin içine gömülü
    açılacağı için ayar panelindeki "Live" düğmesini devre dışı bırakır -
    aksi halde modules/ui.py kendi başına AYRI bir "Live Preview" penceresi
    açardı (_open_webcam_preview).

    Dönen ikinci değer, ayar panelindeki kamera seçim kutusunda o an seçili
    olan kamera indeksini okuyan bir callback'tir; "Başlat"a her basıldığında
    yeniden çağrılır, böylece kiosk her zaman kutuda seçili kamerayı açar.
    """
    settings_window = dlc_ui.init(core.start, core.destroy, "en")
    settings_window._main.show()
    settings_window._main.setGeometry(20, 20, 640, 820)

    settings_window._main.btn_live.setEnabled(False)
    settings_window._main.btn_live.setToolTip(
        "Kamera zaten ana pencerede açık - kiosk modunda devre dışı."
    )

    cam_main = settings_window._main

    def resolve_camera_index():
        indices = cam_main._camera_indices
        if not indices:
            return None
        idx = cam_main.cb_camera.currentIndex()
        return indices[idx] if 0 <= idx < len(indices) else indices[0]

    return settings_window, resolve_camera_index


def has_camera(settings_window) -> bool:
    """Ayar panelinin tespit ettiği en az bir kamera var mı?"""
    return bool(getattr(settings_window._main, "_camera_indices", None))


def set_source_path(path: str) -> None:
    """Aktif kaynak yüz fotoğrafını (kamera işleme thread'inin okuduğu
    modules.globals.source_path) ayarla."""
    modules.globals.source_path = path
