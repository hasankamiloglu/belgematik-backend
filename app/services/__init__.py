"""
İŞ KATMANI (Business / Service Layer)

Görevi: Uygulamanın asıl işini yapmak. Sayfa göstermez, veritabanına SQL yazmaz.
Alt modüller (her biri ilgili haftada doldurulacak):
    auth/             -> Parola hash, JWT, giriş akışı                          [Hafta 5]
    preprocessing/    -> Görsel doğrulama, kalite ölçümü, ön işleme             [Hafta 6]
    belge_servisi.py  -> Yükleme kuralları: kredi, sahiplik, tekrar kontrolü    [Hafta 6]
    ocr/              -> Fotoğraftan metin okuma (Tesseract)                    [Hafta 7]
    extraction/       -> Metinden alan bulma (tarih, vergi no, KDV, toplam)     [Hafta 7]
    validation/       -> Alan ve iş kuralı doğrulama (VKN, KDV + matrah = toplam)[Hafta 7]
    cikarim_servisi.py-> İşleme akışı: OCR -> eşleme -> doğrulama -> kayıt       [Hafta 7]
    export/           -> Excel / CSV / JSON çıktı üretme                       [sonraki]
"""
