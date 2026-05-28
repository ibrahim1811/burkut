"""
BÜRKÜT Widget — Bağımsız başlatıcı.
Bu dosyayı çift tıklayarak widget'ı açabilirsiniz.
Bot çalışmıyor olsa bile widget çalışır.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from widget.main_widget import start_widget
start_widget()
