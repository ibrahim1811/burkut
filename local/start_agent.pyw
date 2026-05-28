# Sessiz başlatıcı — .pyw uzantısı sayesinde konsol penceresi açmaz.
# Görev Zamanlayıcısı veya Başlangıç klasörüne bu dosyayı ekle.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from local.pc_agent import main
main()
