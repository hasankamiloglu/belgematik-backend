"""
conftest.py - pytest'in TÜM testlerden önce otomatik okuduğu ayar dosyası.

Parola hash'leme bilerek yavaştır (600.000 tekrar). Testlerde onlarca hash
hesaplandığı için tekrar sayısını sadece testlerde 1.000'e düşürüyoruz.
Bu satır, parola.py import edilmeden ÖNCE çalışmalı; conftest bunu sağlar.
Gerçek uygulama (python run.py) bu dosyayı hiç okumaz.
"""

import os

os.environ.setdefault("PAROLA_ITERASYON", "1000")
