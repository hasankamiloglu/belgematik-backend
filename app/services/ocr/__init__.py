"""
ocr paketi - Görselden metin okuma.

    tesseract.py    -> Ücretsiz, bilgisayarda çalışan OCR motoru (Hafta 7)
    harici_api.py   -> Bulutta çalışan harici OCR servisi: OCR.space REST API (Hafta 9)
    motor_secici.py -> Hangisinin kullanılacağına karar verir; API hata verirse
                       Tesseract'a geçer (yedek) ve API çağrılarını günlüğe yazar (Hafta 9)

Motorların hepsi aynı biçimde sonuç döndürür: {"metin", "guven", "motor", ...}
Bu yüzden yeni motor eklenince geri kalan kod değişmez.
"""
