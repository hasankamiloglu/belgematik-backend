"""
ornek_gorsel.py - Testler için SENTETİK (uydurma) fiş görselleri üretir.

Gerçek fiş fotoğrafı kullanmıyoruz (kişisel veri / KVKK). Pillow ile beyaz
zemin üzerine yazı yazıp, bulanık / karanlık / soluk sürümlerini üretiyoruz.
"""

import io

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def fis(genislik=800, yukseklik=1200, bozulma=None):
    """
    Fiş benzeri görsel üretir.
        bozulma -> None, "bulanik", "cok_bulanik", "karanlik", "soluk"
    """
    gorsel = Image.new("RGB", (genislik, yukseklik), (245, 243, 238))
    cizim = ImageDraw.Draw(gorsel)
    try:
        yazi_tipi = ImageFont.load_default(size=28)
    except TypeError:  # eski Pillow sürümleri boyut parametresi almaz
        yazi_tipi = ImageFont.load_default()
    y = 40
    while y < yukseklik - 40:
        cizim.text((40, y), f"URUN {y:04d} ...... {y % 97},50 TL KDV %20", fill=(20, 20, 20), font=yazi_tipi)
        y += 36

    if bozulma == "bulanik":
        gorsel = gorsel.filter(ImageFilter.GaussianBlur(2))
    elif bozulma == "cok_bulanik":
        gorsel = gorsel.filter(ImageFilter.GaussianBlur(5))
    elif bozulma == "karanlik":
        gorsel = ImageEnhance.Brightness(gorsel).enhance(0.2)
    elif bozulma == "soluk":
        gorsel = ImageEnhance.Contrast(gorsel).enhance(0.15)
    return gorsel


def bayt(gorsel, bicim="JPEG"):
    """Görseli dosya baytlarına çevirir (yükleme testleri için)."""
    tampon = io.BytesIO()
    gorsel.save(tampon, format=bicim)
    return tampon.getvalue()
