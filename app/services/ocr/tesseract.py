"""
tesseract.py - Tesseract OCR ile görselden metin okuma.

Tesseract, Google'ın da geliştirdiği ücretsiz ve açık kaynak bir OCR programıdır.
Python'dan "pytesseract" kütüphanesi ile çağrılır (pytesseract sadece aracıdır;
asıl program bilgisayarda ayrıca kurulu olmalıdır).

Windows kurulumu: UB Mannheim "tesseract-ocr-w64-setup" -> varsayılan klasör
    C:\\Program Files\\Tesseract-OCR\\tesseract.exe
Bu dosya o klasörü kendisi bulur; PATH ayarı gerekmez.
"""

import os
import shutil

import pytesseract
from PIL import Image

MOTOR_ADI = "tesseract"

# Windows'ta Tesseract'ın varsayılan kurulum yerleri
WINDOWS_YOLLARI = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


class OcrHatasi(Exception):
    """OCR çalıştırılamadığında (program yok, dosya okunamadı) fırlatılır."""

    def __init__(self, mesaj):
        super().__init__(mesaj)
        self.mesaj = mesaj


def _programi_bul():
    """
    Tesseract programının yerini bulur:
        1) .env içindeki TESSERACT_CMD   2) PATH   3) Windows varsayılan klasörü
    Bulamazsa None.
    """
    adaylar = [os.getenv("TESSERACT_CMD"), shutil.which("tesseract"), *WINDOWS_YOLLARI]
    for yol in adaylar:
        if yol and os.path.exists(yol):
            return yol
    return None


def kurulu_mu():
    """Tesseract bu bilgisayarda çalıştırılabilir mi? (testler ve sağlık kontrolü için)"""
    return _programi_bul() is not None


def _dil():
    """
    Türkçe dil paketi kuruluysa "eng+tur", değilse "eng".

    Neden İngilizce ÖNCE? Denemelerde Türkçe model "%20" yazısını "420" okudu ve
    rakamlarda daha çok hata yaptı. İngilizce model rakam ve işaretlerde daha başarılı;
    Türkçe model de ikinci dil olarak ş, ğ, ı, İ harflerini tanımaya yardım ediyor.
    (4 farklı yazı tipi x 5 örnek belgede: "tur+eng" 4 hata, "eng+tur" 0 hata.)
    """
    try:
        diller = pytesseract.get_languages()
    except Exception:  # noqa: BLE001 - dil listesi alınamazsa İngilizce ile devam
        return "eng"
    return "eng+tur" if "tur" in diller else "eng"


def metin_oku(gorsel_yolu):
    """
    Görseldeki yazıyı okur.

    Parametre:
        gorsel_yolu -> ön işlenmiş görselin diskteki yolu (Hafta 6'da üretilen *_islenmis.png)
    Döndürür:
        {"metin": "...", "guven": 0.0-1.0, "motor": "tesseract", "dil": "tur+eng"}
    Hata:
        OcrHatasi -> Tesseract kurulu değilse veya görsel okunamazsa
    """
    program = _programi_bul()
    if program is None:
        raise OcrHatasi(
            "Tesseract OCR kurulu değil. Kurulum: docs/kurulum-windows.md (Tesseract bölümü)."
        )
    pytesseract.pytesseract.tesseract_cmd = program

    dil = _dil()
    try:
        with Image.open(gorsel_yolu) as gorsel:
            # --psm 6 -> "sayfa tek bir metin bloğu" varsay: fiş gibi alt alta satırlar için uygun
            ayar = "--psm 6"
            metin = pytesseract.image_to_string(gorsel, lang=dil, config=ayar)
            # image_to_data -> her kelimenin güven puanını (0-100) da verir
            veri = pytesseract.image_to_data(gorsel, lang=dil, config=ayar,
                                             output_type=pytesseract.Output.DICT)
    except (OSError, pytesseract.TesseractError) as hata:
        raise OcrHatasi(f"Görsel okunamadı: {hata}")

    # Boş olmayan kelimelerin güven ortalaması. (-1 = kelime değil, atlanır)
    puanlar = [float(g) for g, k in zip(veri["conf"], veri["text"]) if k.strip() and float(g) >= 0]
    guven = round(sum(puanlar) / len(puanlar) / 100, 3) if puanlar else 0.0

    return {"metin": metin.strip(), "guven": guven, "motor": MOTOR_ADI, "dil": dil}
