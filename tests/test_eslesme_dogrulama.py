"""
test_eslesme_dogrulama.py - Alan eşleme ve doğrulama testleri.
Veritabanı ve OCR GEREKMEZ: OCR'ın okuduğu metin elle veriliyor.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.extraction.eslestirici import alanlari_esle, kelimeleri_ayir
from app.services.extraction.metin_araclari import para_bul, sadelestir, tarih_bul
from app.services.validation.dogrulayici import alan_dogrula, dogrula, is_kurallari
from app.services.validation.kimlik_no import tckn_gecerli_mi, vkn_gecerli_mi

BUGUN = date(2026, 11, 5)

FIS_ALANLARI = [
    {"alan_adi": "firma_adi", "veri_tipi": "metin", "zorunlu_mu": True, "anahtar_kelimeler": None},
    {"alan_adi": "vergi_no", "veri_tipi": "metin", "zorunlu_mu": True,
     "dogrulama_kurali": "^[0-9]{10,11}$", "anahtar_kelimeler": "VKN,VERGI NO,V.D"},
    {"alan_adi": "tarih", "veri_tipi": "tarih", "zorunlu_mu": True, "anahtar_kelimeler": "TARIH"},
    {"alan_adi": "fis_no", "veri_tipi": "metin", "zorunlu_mu": False, "anahtar_kelimeler": "FIS NO"},
    {"alan_adi": "kdv_orani", "veri_tipi": "sayi", "zorunlu_mu": False, "anahtar_kelimeler": "KDV %,KDV,%"},
    {"alan_adi": "kdv_tutari", "veri_tipi": "para", "zorunlu_mu": True,
     "anahtar_kelimeler": "TOPKDV,TOPLAM KDV,KDV,-MATRAH"},
    {"alan_adi": "toplam_tutar", "veri_tipi": "para", "zorunlu_mu": True,
     "anahtar_kelimeler": "GENEL TOPLAM,TOPLAM,-ARA,-KDV"},
]

FIS_METNI = """ORNEK MARKET GIDA LTD. STI.
V.D. BINGOL  VKN 1234567808
TARİH: 12.10.2026   SAAT: 14:32
Fiş No: 0042
DETERJAN          %20   *150,00
SAMPUAN           %20    *97,50
ARA TOPLAM              *247,50
TOPKDV                   *41,25
TOPLAM                  *247,50"""


# ------------------------------------------------------- yardımcı fonksiyonlar
def test_sadelestir_turkce_ve_buyuk_harf():
    assert sadelestir("Fiş  No: İşlem") == "FIS NO: ISLEM"


@pytest.mark.parametrize("metin, beklenen", [
    ("TOPLAM *1.234,56", [Decimal("1234.56")]),
    ("TOPLAM *800, 00", [Decimal("800.00")]),       # OCR virgülden sonra boşluk koymuş
    ("KDV %20 *41,25", [Decimal("41.25")]),          # %20 para sanılmamalı
    ("BENZIN 20,00 LT *800,00", [Decimal("20.00"), Decimal("800.00")]),
])
def test_para_bul(metin, beklenen):
    assert para_bul(metin) == beklenen


def test_tarih_bul_gecersiz_tarihi_atlar():
    assert tarih_bul("31.02.2026 ve 12.10.26") == date(2026, 10, 12)


def test_anahtar_kelime_ayirma():
    assert kelimeleri_ayir("GENEL TOPLAM,TOPLAM,-ARA") == (["GENEL TOPLAM", "TOPLAM"], ["ARA"])


# ------------------------------------------------------------------- eşleme
def test_fis_alanlari_eslenir():
    sonuc = alanlari_esle(FIS_METNI, FIS_ALANLARI)
    degerler = {ad: s["deger"] for ad, s in sonuc.items()}
    assert degerler == {
        "firma_adi": "ORNEK MARKET GIDA LTD. STI.",
        "vergi_no": "1234567808",
        "tarih": "2026-10-12",
        "fis_no": "0042",
        "kdv_orani": "20",
        "kdv_tutari": "41.25",
        "toplam_tutar": "247.50",
    }
    assert sonuc["toplam_tutar"]["yontem"] == "anahtar_kelime"
    assert sonuc["firma_adi"]["yontem"] == "konum"


def test_ara_toplam_eleyici_kelimeyle_alinmaz():
    """'ARA TOPLAM' satırı -ARA ile elenir; asıl 'TOPLAM' satırı alınır."""
    metin = "ARA TOPLAM *100,00\nTOPLAM *120,00\nNAKIT *200,00"
    alan = [FIS_ALANLARI[-1]]
    assert alanlari_esle(metin, alan)["toplam_tutar"]["deger"] == "120.00"


def test_deger_alt_satirda_olabilir():
    metin = "GENEL TOPLAM\n*1.200,00"
    sonuc = alanlari_esle(metin, [FIS_ALANLARI[-1]])["toplam_tutar"]
    assert sonuc["deger"] == "1200.00" and sonuc["guven"] == 0.8


def test_karisik_kdv_oraninda_oran_bos_kalir():
    metin = "EKMEK %1 *10,00\nDETERJAN %20 *150,00\nTOPKDV *25,10\nTOPLAM *160,00"
    assert alanlari_esle(metin, FIS_ALANLARI)["kdv_orani"]["yontem"] == "karisik_oran"


def test_kartvizit_kalip_ile():
    alanlar = [
        {"alan_adi": "ad_soyad", "veri_tipi": "metin", "anahtar_kelimeler": None},
        {"alan_adi": "firma", "veri_tipi": "metin", "anahtar_kelimeler": None},
        {"alan_adi": "telefon", "veri_tipi": "metin", "anahtar_kelimeler": "TEL"},
        {"alan_adi": "email", "veri_tipi": "metin", "anahtar_kelimeler": "E-POSTA"},
    ]
    metin = "AYSE ORNEK\nMUHASEBE MUDURU YARDIMCISI\nORNEK DANISMANLIK LTD. STI.\n+90 (532) 123 45 67\nayse@ornek.test"
    d = {a: s["deger"] for a, s in alanlari_esle(metin, alanlar).items()}
    assert d == {"ad_soyad": "AYSE ORNEK", "firma": "ORNEK DANISMANLIK LTD. STI.",
                 "telefon": "05321234567", "email": "ayse@ornek.test"}


# --------------------------------------------------------------- doğrulama
def test_vkn_ve_tckn_kontrol_hanesi():
    assert vkn_gecerli_mi("1234567808") is True
    assert vkn_gecerli_mi("1234567809") is False   # son hane yanlış
    assert vkn_gecerli_mi("123456780") is False    # 9 hane
    assert tckn_gecerli_mi("10000000146") is True
    assert tckn_gecerli_mi("10000000147") is False


@pytest.mark.parametrize("alan, deger, gecerli", [
    ({"alan_adi": "x", "veri_tipi": "metin", "zorunlu_mu": True}, None, False),     # zorunlu boş
    ({"alan_adi": "x", "veri_tipi": "metin", "zorunlu_mu": False}, None, True),     # zorunlu değil
    ({"alan_adi": "tarih", "veri_tipi": "tarih"}, "2027-01-01", False),             # gelecek
    ({"alan_adi": "tarih", "veri_tipi": "tarih"}, "2026-10-12", True),
    ({"alan_adi": "toplam_tutar", "veri_tipi": "para"}, "0.00", False),             # sıfır tutar
    ({"alan_adi": "kdv_orani", "veri_tipi": "sayi"}, "25", False),                  # olmayan oran
    ({"alan_adi": "vergi_no", "veri_tipi": "metin", "dogrulama_kurali": "^[0-9]{10,11}$"}, "12345", False),
    ({"alan_adi": "email", "veri_tipi": "metin"}, "ayse@", False),
    ({"alan_adi": "tc_no", "veri_tipi": "metin", "dogrulama_kurali": "^[0-9]{11}$"}, "123", False),  # kullanıcı regex'i
])
def test_alan_kurallari(alan, deger, gecerli):
    assert alan_dogrula(alan, deger, BUGUN)[0] is gecerli


def test_kdv_orani_ile_tutari_tutarli_mi():
    dogru = is_kurallari({"kdv_orani": "20", "kdv_tutari": "41.25", "toplam_tutar": "247.50"})
    yanlis = is_kurallari({"kdv_orani": "20", "kdv_tutari": "25.00", "toplam_tutar": "90.00"})
    assert all(k["gecerli"] for k in dogru)
    assert not yanlis[1]["gecerli"] and "15.00" in yanlis[1]["mesaj"]


def test_matrah_kdv_toplam():
    assert is_kurallari({"matrah": "1000.00", "kdv_tutari": "200.00", "toplam_tutar": "1200.00"})[-1]["gecerli"]
    assert not is_kurallari({"matrah": "1000.00", "kdv_tutari": "200.00", "toplam_tutar": "1300.00"})[-1]["gecerli"]


def test_dogrula_hepsi():
    bulunanlar = alanlari_esle(FIS_METNI, FIS_ALANLARI)
    alan_sonuclari, kurallar, hepsi = dogrula(FIS_ALANLARI, bulunanlar, BUGUN)
    assert hepsi is True
    assert all(a["gecerli"] for a in alan_sonuclari.values())
    assert len(kurallar) == 2


def test_ocr_yuzde_isaretini_4_okursa_oran_yine_bulunur():
    """Türkçe OCR modeli "%20" yazısını "420" okuyabiliyor; oran yine 20 bulunmalı."""
    metin = "DEFTER 420 *60,00\nKALEM %20 *30,00\nTOPKDV *25,00\nTOPLAM *90,00"
    sonuc = alanlari_esle(metin, FIS_ALANLARI)
    assert sonuc["kdv_orani"]["deger"] == "20"
    assert sonuc["toplam_tutar"]["deger"] == "90.00"  # 420 ve *60,00 karışmamalı
