"""
ornek_belgeler.py - Test ve demo için SENTETİK (uydurma) fiş, fatura ve kartvizit görselleri.

Gerçek belge kullanmıyoruz (KVKK). Bütün firma adları, numaralar ve kişiler uydurmadır.
Vergi numaraları kontrol hanesi DOĞRU olacak şekilde seçildi (1234567808 geçerli,
1234567809 geçersiz) ki doğrulama kuralları gösterilebilsin.

Doğrudan çalıştırınca görselleri klasöre yazar:
    python -m tests.ornek_belgeler ornek-belgeler
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont


BELGELER = {
    # ad: (satırlar, açıklama)
    "fis_dogru": [
        "ORNEK MARKET GIDA LTD. STI.",
        "ATATURK CAD. NO:12 BINGOL",
        "V.D. BINGOL  VKN 1234567808",
        "TARIH: 12.10.2026   SAAT: 14:32",
        "FIS NO: 0042",
        "DETERJAN 3 KG     %20   *150,00",
        "SAMPUAN           %20    *97,50",
        "TOPKDV                   *41,25",
        "TOPLAM                  *247,50",
        "NAKIT                   *250,00",
    ],
    "fis_kdv_hatali": [
        "ORNEK KIRTASIYE TIC. LTD.",
        "V.D. MERKEZ  VKN 1234567816",
        "TARIH: 14.10.2026",
        "FIS NO: 0117",
        "DEFTER            %20    *60,00",
        "KALEM             %20    *30,00",
        "TOPKDV                   *25,00",
        "TOPLAM                   *90,00",
    ],
    "fis_vkn_hatali": [
        "ORNEK AKARYAKIT A.S.",
        "V.D. BINGOL  VKN 1234567809",
        "TARIH: 13.10.2026",
        "FIS NO: 2231",
        "BENZIN 20,00 LT   %20   *800,00",
        "TOPKDV                  *133,33",
        "TOPLAM                  *800,00",
    ],
    "fatura": [
        "ORNEK YAZILIM HIZMETLERI A.S.",
        "VERGI NO: 1234567824",
        "FATURA NO: ABC2026000000123",
        "FATURA TARIHI: 20.10.2026",
        "HIZMET BEDELI        1.000,00",
        "MATRAH               1.000,00",
        "HESAPLANAN KDV %20     200,00",
        "GENEL TOPLAM         1.200,00",
    ],
    "kartvizit": [
        "AYSE ORNEK",
        "MUHASEBE MUDURU",
        "ORNEK DANISMANLIK LTD. STI.",
        "TEL: 0532 123 45 67",
        "E-POSTA: ayse@ornek.test",
    ],
}


def _yazi_tipi(boyut):
    """
    Pillow'un KENDİ İÇİNDE gelen yazı tipi. Bilgisayara kurulu yazı tiplerini
    kullanmıyoruz: Windows'ta Consolas, Linux'ta DejaVu farklı çizilir ve OCR
    sonucu bilgisayara göre değişirdi. Böylece test her bilgisayarda aynı görseli üretir.
    """
    return ImageFont.load_default(size=boyut)


def belge_gorseli(satirlar, boyut=28):
    """Satırları beyaz zemine siyah yazıyla çizer (fiş görünümü)."""
    yazi = _yazi_tipi(boyut)
    yukseklik = 80 + len(satirlar) * int(boyut * 1.6)
    gorsel = Image.new("RGB", (760, max(yukseklik, 500)), (250, 249, 245))
    cizim = ImageDraw.Draw(gorsel)
    y = 40
    for satir in satirlar:
        cizim.text((40, y), satir, fill=(25, 25, 25), font=yazi)
        y += int(boyut * 1.6)
    return gorsel


if __name__ == "__main__":
    klasor = sys.argv[1] if len(sys.argv) > 1 else "ornek-belgeler"
    os.makedirs(klasor, exist_ok=True)
    for ad, satirlar in BELGELER.items():
        belge_gorseli(satirlar).save(os.path.join(klasor, f"{ad}.jpg"), quality=92)
        print("yazıldı:", os.path.join(klasor, f"{ad}.jpg"))
