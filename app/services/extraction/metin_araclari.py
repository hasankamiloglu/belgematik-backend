"""
metin_araclari.py - OCR metnini karşılaştırılabilir hale getiren yardımcılar.

Fişlerdeki yazım çok çeşitlidir: "TOPLAM", "Toplam", "TOPLAM:", "TOPLAM *247,50".
Bu fonksiyonlar metni sadeleştirir ve sayıları/tarihleri Python değerine çevirir.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

# Türkçe harfleri sade ASCII karşılığına çeviren tablo.
# OCR bazen "İ" yerine "I", "Ş" yerine "S" okur; ikisini eşit saymak için sadeleştiriyoruz.
_TURKCE = str.maketrans("ÇĞİÖŞÜçğıöşüÂâÎîÛû", "CGIOSUcgiosuAaIiUu")


def sadelestir(metin):
    """
    Metni karşılaştırma için sadeleştirir:
        "Fiş No: 0042"  ->  "FIS NO: 0042"
    1) Türkçe harfleri ASCII'ye çevir   2) BÜYÜK harfe çevir   3) fazla boşlukları tek boşluk yap
    """
    metin = (metin or "").translate(_TURKCE).upper()
    return re.sub(r"[ \t]+", " ", metin).strip()


# ----------------------------------------------------------------- PARA
# Türkiye'de para: binlik ayırıcı nokta, kuruş ayırıcı virgül -> 1.234,56
# Bazı fişlerde tersi (1,234.56) veya hiç binlik yok (1234,56). Hepsini yakalıyoruz.
# Açıklama:
#   \d{1,3}(?:\.\d{3})+   -> 1.234.567 gibi binlikli kısım
#   |\d+                  -> veya düz rakamlar
#   \s?[,.]\s?\d{2}       -> virgül/nokta + 2 haneli kuruş (ZORUNLU; böylece "KDV %20" para sanılmaz)
#                           \s? -> OCR bazen virgülün yanına boşluk koyar: "800, 00"
PARA_KALIBI = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d+)\s?[,.]\s?(\d{2})(?![\d])")


def para_bul(satir):
    """
    Satırdaki TÜM para değerlerini Decimal listesi olarak döndürür.
        "TOPLAM *1.234,56"  ->  [Decimal("1234.56")]
    Decimal -> kuruş hesabında yuvarlama hatası olmayan sayı tipi (float 0.1+0.2 = 0.30000000000000004 yapar).
    """
    sonuc = []
    for tam, kurus in PARA_KALIBI.findall(satir):
        tam = tam.replace(".", "")  # binlik ayırıcılarını sil
        try:
            sonuc.append(Decimal(f"{tam}.{kurus}"))
        except InvalidOperation:
            pass
    return sonuc


def para_coz(metin):
    """Tek bir para metnini çözer: "247,50" -> Decimal("247.50"). Çözemezse None."""
    degerler = para_bul(str(metin or "").replace("TL", "").replace("₺", ""))
    if degerler:
        return degerler[-1]
    # Kuruşsuz yazılmış olabilir: "250" -> 250.00
    duz = re.fullmatch(r"\s*(\d+)\s*", str(metin or ""))
    return Decimal(duz.group(1) + ".00") if duz else None


# ----------------------------------------------------------------- TARİH
# 12.10.2026 / 12/10/2026 / 12-10-2026 / 12.10.26
TARIH_KALIBI = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)")


def tarih_bul(satir):
    """
    Satırdaki ilk geçerli tarihi date olarak döndürür, yoksa None.
        "TARIH: 12.10.2026 SAAT 14:32" -> date(2026, 10, 12)
    """
    for gun, ay, yil in TARIH_KALIBI.findall(satir):
        yil = int(yil) + 2000 if len(yil) == 2 else int(yil)
        try:
            return date(yil, int(ay), int(gun))  # 31.02.2026 gibi imkânsız tarih -> ValueError
        except ValueError:
            continue
    return None


def tarih_coz(metin):
    """ISO ("2026-10-12") veya Türk biçimi ("12.10.2026") tarihi çözer. Çözemezse None."""
    metin = str(metin or "").strip()
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", metin)
    if iso:
        try:
            return date(*map(int, iso.groups()))
        except ValueError:
            return None
    return tarih_bul(metin)


# ----------------------------------------------------------------- KDV ORANI
# KDV oranı fişte "%20" diye yazılır. OCR (özellikle Türkçe modelde) "%" işaretini
# sık sık "4" okur: "%20" -> "420". Bu yüzden 4 ile başlayan ve arkasından GEÇERLİ
# bir oran gelen 3 haneli sayıyı da oran sayıyoruz (420 -> 20, 410 -> 10, 41 -> 1).
# (?![\d,.]) -> arkasından rakam/virgül gelmesin; böylece "*20,00" gibi tutarlar oran sanılmaz.
ORAN_KALIBI = re.compile(
    r"%\s*(\d{1,2})(?![\d,.])"                                   # %20
    r"|(?<![\d.,*])4(1|8|10|18|20)(?![\d,.])"                     # 420 (OCR hatası)
)


def kdv_oranlari_bul(metin):
    """Metindeki KDV oranları: "DEFTER %20 *60,00\nKALEM 420 *30,00" -> [20, 20]"""
    return [int(a or b) for a, b in ORAN_KALIBI.findall(metin)]


# ----------------------------------------------------------------- SAYI
def sayi_bul(satir):
    """Satırdaki sayı: önce KDV oranı biçimi (%20), yoksa ilk tam sayı. Yoksa None."""
    oranlar = kdv_oranlari_bul(satir)
    if oranlar:
        return oranlar[0]
    eslesme = re.search(r"\b(\d+)\b", satir)
    return int(eslesme.group(1)) if eslesme else None
