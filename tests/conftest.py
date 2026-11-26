"""
conftest.py - pytest'in TÜM testlerden önce otomatik okuduğu ayar dosyası.

Parola hash'leme bilerek yavaştır (600.000 tekrar). Testlerde onlarca hash
hesaplandığı için tekrar sayısını sadece testlerde 1.000'e düşürüyoruz.
Bu satır, parola.py import edilmeden ÖNCE çalışmalı; conftest bunu sağlar.
Gerçek uygulama (python run.py) bu dosyayı hiç okumaz.
"""

import os

os.environ.setdefault("PAROLA_ITERASYON", "1000")

# Hafta 9: Testler GERÇEK OCR API'sini çağırmamalı (hem kotayı harcar hem internete bağlı olur).
# .env'de anahtar olsa bile testlerde Tesseract kullanılır. Harici API testleri
# (test_harici_api.py) internete hiç çıkmadan SAHTE cevaplarla çalışır.
os.environ["OCR_MOTORU"] = "tesseract"

# Hafta 10: Testler gerçek yapay zekâ servisini de çağırmamalı. Yapay zekâ testleri
# (test_yapay_zeka.py) sahte cevaplar kullanır ve anahtarı kendileri ayarlar.
os.environ["AI_API_ANAHTARI"] = ""
