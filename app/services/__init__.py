"""
İŞ KATMANI (Business / Service Layer)

Görevi: Uygulamanın asıl işini yapmak. Sayfa göstermez, veritabanına SQL yazmaz.
Alt modüller (her biri ilgili haftada doldurulacak):
    auth/             -> Parola hash, JWT, giriş akışı                          [Hafta 5]
    preprocessing/    -> Görsel doğrulama, kalite ölçümü, ön işleme             [Hafta 6]
    belge_servisi.py  -> Yükleme kuralları: kredi, sahiplik, tekrar kontrolü    [Hafta 6]
    ocr/              -> Fotoğraftan metin okuma (Tesseract veya yapay zekâ)    [Hafta 7]
    extraction/       -> Metinden alan bulma (tarih, vergi no, KDV, toplam)    [sonraki]
    validation/       -> Şema ve iş kuralı doğrulama (KDV + matrah = toplam?)  [sonraki]
    export/           -> Excel / CSV / JSON çıktı üretme                       [sonraki]
"""
