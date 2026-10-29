"""
models.py - Veri modeli hakkında.

Bu projede ORM (SQLAlchemy gibi) yerine SAF SQL yaklaşımı seçildi:
    - Tablolar  : db/migrations/001_tablolari_olustur.sql  (CREATE TABLE)
    - İndeksler : db/migrations/002_indeksleri_olustur.sql (CREATE INDEX)
    - CRUD      : app/data/repositories/*.py               (INSERT/SELECT/UPDATE/DELETE)

Neden saf SQL?
    + Hangi SQL'in çalıştığı açıkça görülür; indeks ve sorgu performansı kontrol altında.
    + Ders kapsamındaki DDL/DML, kısıt ve transaction kavramları doğrudan uygulanır.
    - Dezavantaj: SQL'i elle yazmak gerekir; ORM bunu otomatik üretirdi.

Aşağıdaki sabitler, veritabanındaki CHECK kısıtlarında izin verilen değerlerin
Python'daki karşılığıdır. İş katmanı (services) kullanıcıdan gelen veriyi
veritabanına göndermeden ÖNCE bu listelerle kontrol edebilir.
"""

ROLLER = ("bireysel", "kobi", "muhasebeci")
PAKETLER = ("ucretsiz", "pro")
DOSYA_TURLERI = ("png", "jpg", "jpeg", "pdf")
BELGE_DURUMLARI = ("yuklendi", "on_islendi", "islendi", "hatali")  # on_islendi: Hafta 6
VERI_TIPLERI = ("metin", "tarih", "para", "sayi")
OCR_MOTORLARI = ("tesseract", "yapay_zeka")
CIKARIM_DURUMLARI = ("bekliyor", "dogrulandi", "duzeltildi")
