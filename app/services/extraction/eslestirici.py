"""
eslestirici.py - OCR metninden şema alanlarını bulur (ALAN EŞLEME).

NASIL ÇALIŞIR? (3 yöntem, güvenden en yükseğe göre denenir)
    1) ANAHTAR KELİME: Şemadaki alanın anahtar kelimelerini (ör. "TOPLAM") içeren
       satırı bul, o satırdaki değeri veri tipine göre al.         güven: 0.90
       Değer aynı satırda yoksa bir alt satıra bakılır.             güven: 0.80
    2) KALIP: Anahtar kelime bulunamazsa bilinen kalıbı metnin her yerinde ara
       (10 haneli vergi no, gg.aa.yyyy tarih, e-posta, telefon).    güven: 0.60
    3) KONUM: Firma adı genelde fişin EN ÜST satırıdır.              güven: 0.60

Satırlar AŞAĞIDAN YUKARIYA taranır: fişte toplamlar en alttadır; "TOPLAM" kelimesi
yukarıda ürün satırlarında da geçebilir, en alttaki asıl toplamdır.

Kullanım:
    alanlar = [{"alan_adi": "toplam_tutar", "veri_tipi": "para",
                "anahtar_kelimeler": "GENEL TOPLAM,TOPLAM,-ARA,-KDV"}, ...]
    sonuc = alanlari_esle(ocr_metni, alanlar)
    sonuc["toplam_tutar"]  ->  {"deger": "247.50", "guven": 0.9, "yontem": "anahtar_kelime"}
"""

import re

from app.services.extraction.metin_araclari import (
    kdv_oranlari_bul,
    para_bul,
    sadelestir,
    sayi_bul,
    tarih_bul,
)

GUVEN_ANAHTAR = 0.90
GUVEN_ALT_SATIR = 0.80
GUVEN_KALIP = 0.60
GUVEN_KONUM = 0.60

VERGI_NO_KALIBI = re.compile(r"(?<!\d)(\d{10,11})(?!\d)")
EMAIL_KALIBI = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Türkiye telefonu: +90 / 0 ile başlayabilir, 10 hane: 532 123 45 67 / (212) 555 12 34
TELEFON_KALIBI = re.compile(
    r"(?:\+?90[\s-]?|0)?\(?([2-5]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{2})[\s.-]?(\d{2})(?!\d)"
)
# Şirket türü ekleri: kartvizitte firma satırını bulmak için
SIRKET_EKLERI = ("A.S", "AS.", "LTD", "STI", "TIC", "SAN", "HOLDING", "A.Ş", "LIMITED", "SIRKETI")


def kelimeleri_ayir(anahtar_kelimeler):
    """
    "GENEL TOPLAM,TOPLAM,-ARA,-KDV" -> (["GENEL TOPLAM", "TOPLAM"], ["ARA", "KDV"])
    "-" ile başlayanlar ELEYİCİ kelimelerdir: bu kelimeyi içeren satır kullanılmaz.
    """
    pozitif, negatif = [], []
    for kelime in (anahtar_kelimeler or "").split(","):
        kelime = sadelestir(kelime)
        if not kelime:
            continue
        if kelime.startswith("-"):
            negatif.append(kelime[1:].strip())
        else:
            pozitif.append(kelime)
    return pozitif, negatif


def _kelime_var_mi(satir, kelime):
    """
    Kelime satırda AYRI bir kelime olarak geçiyor mu?
    "KDV" -> "KDV %20" içinde VAR, "TOPKDV" içinde YOK (önünde harf var).
    (?<![A-Z]) -> öncesinde harf olmasın,  (?![A-Z]) -> sonrasında harf olmasın
    """
    return re.search(rf"(?<![A-Z]){re.escape(kelime)}(?![A-Z])", satir) is not None


def _kelimeden_sonrasi(satir, kelime):
    """Satırda kelimeden SONRA gelen kısım: "FIS NO: 0042" + "FIS NO" -> "0042" """
    eslesme = re.search(rf"(?<![A-Z]){re.escape(kelime)}(?![A-Z])", satir)
    return satir[eslesme.end():].strip(" :#.*-\t") if eslesme else ""


# ------------------------------------------------------------- değer okuma
def _degeri_oku(satir, kelime, veri_tipi, alan_adi):
    """
    Bir satırdan, alanın veri tipine uygun değeri okur. Bulamazsa None.
        para  -> satırdaki SON para değeri ("TOPLAM 3 ADET *247,50" -> 247.50)
        tarih -> satırdaki ilk tarih (ISO biçimine çevrilir)
        sayi  -> satırdaki sayı ("KDV %20" -> 20)
        metin -> kelimeden sonraki yazı; vergi_no için 10-11 haneli sayı
    """
    sonrasi = _kelimeden_sonrasi(satir, kelime)
    if veri_tipi == "para":
        degerler = para_bul(sonrasi)
        return f"{degerler[-1]:.2f}" if degerler else None
    if veri_tipi == "tarih":
        bulunan = tarih_bul(sonrasi) or tarih_bul(satir)
        return bulunan.isoformat() if bulunan else None
    if veri_tipi == "sayi":
        sayi = sayi_bul(satir if kdv_oranlari_bul(satir) else sonrasi)
        return str(sayi) if sayi is not None else None
    # metin
    if alan_adi == "vergi_no":
        eslesme = VERGI_NO_KALIBI.search(sonrasi) or VERGI_NO_KALIBI.search(satir)
        return eslesme.group(1) if eslesme else None
    if alan_adi == "telefon":
        return _telefon_bul(satir)
    if alan_adi == "email":
        eslesme = EMAIL_KALIBI.search(satir)
        return eslesme.group(0).lower() if eslesme else None
    return sonrasi[:100] or None


def _anahtar_kelime_ile(satirlar, alan):
    """Yöntem 1: anahtar kelime satırını bul (aşağıdan yukarı) ve değeri oku."""
    pozitif, negatif = kelimeleri_ayir(alan.get("anahtar_kelimeler"))
    for kelime in pozitif:  # liste önceliğe göre sıralı: "GENEL TOPLAM" önce, "TOPLAM" sonra
        for i in range(len(satirlar) - 1, -1, -1):  # aşağıdan yukarıya
            satir = satirlar[i]
            if not _kelime_var_mi(satir, kelime):
                continue
            if any(_kelime_var_mi(satir, n) for n in negatif):
                continue  # eleyici kelime var (ör. "ARA TOPLAM") -> bu satırı atla
            deger = _degeri_oku(satir, kelime, alan["veri_tipi"], alan["alan_adi"])
            if deger:
                return deger, GUVEN_ANAHTAR
            # Değer bir alt satırda olabilir ("TOPLAM" \n "247,50")
            if i + 1 < len(satirlar):
                alt = satirlar[i + 1]
                deger = _degeri_oku(f"{kelime} {alt}", kelime, alan["veri_tipi"], alan["alan_adi"])
                if deger:
                    return deger, GUVEN_ALT_SATIR
    return None, 0.0


# ------------------------------------------------------- kalıp / konum
def _telefon_bul(metin):
    eslesme = TELEFON_KALIBI.search(metin)
    return "0" + "".join(eslesme.groups()) if eslesme else None  # -> 05321234567


def _ilk_anlamli_satir(satirlar, haric=()):
    """En üstteki, harf içeren ve sadece sayı/tarih olmayan satır (firma adı adayı)."""
    for satir in satirlar:
        harf_sayisi = sum(c.isalpha() for c in satir)
        if harf_sayisi >= 3 and harf_sayisi >= len(satir.replace(" ", "")) * 0.5 and satir not in haric:
            return satir
    return None


def _kalip_ile(metin, satirlar, ham_satirlar, alan):
    """Yöntem 2 ve 3: anahtar kelime olmadan, kalıba veya konuma göre bul. -> (değer, güven, yöntem)"""
    ad, tip = alan["alan_adi"], alan["veri_tipi"]

    if ad == "vergi_no":
        # Telefon numaraları (0 ile başlayan 11 hane) vergi no sanılmasın
        for aday in VERGI_NO_KALIBI.findall(metin):
            if not (len(aday) == 11 and aday.startswith("0")):
                return aday, GUVEN_KALIP, "kalip"
    if ad == "email":
        eslesme = EMAIL_KALIBI.search(" ".join(ham_satirlar))
        return (eslesme.group(0).lower(), GUVEN_KALIP, "kalip") if eslesme else (None, 0.0, None)
    if ad == "telefon":
        bulunan = _telefon_bul(metin)
        return (bulunan, GUVEN_KALIP, "kalip") if bulunan else (None, 0.0, None)
    if tip == "tarih":
        bulunan = tarih_bul(metin)
        if bulunan:
            return bulunan.isoformat(), GUVEN_KALIP, "kalip"

    # Kartvizit: firma = şirket eki geçen satır; ad soyad = 2-3 kelimelik, sadece harf olan satır
    if ad == "firma":
        for i, satir in enumerate(satirlar):
            if any(ek in satir for ek in SIRKET_EKLERI):
                return ham_satirlar[i], GUVEN_KALIP, "kalip"
    if ad == "ad_soyad":
        for i, satir in enumerate(satirlar):
            kelimeler = satir.split()
            if 2 <= len(kelimeler) <= 3 and all(k.isalpha() for k in kelimeler) \
                    and not any(ek in satir for ek in SIRKET_EKLERI):
                return ham_satirlar[i], GUVEN_KONUM, "konum"

    # Fiş/fatura: firma adı en üstteki anlamlı satırdır
    if ad in ("firma_adi", "firma"):
        satir = _ilk_anlamli_satir(ham_satirlar)
        if satir:
            return satir, GUVEN_KONUM, "konum"
    return None, 0.0, None


# ================================================================ ANA FONKSİYON
def alanlari_esle(metin, alanlar):
    """
    OCR metninden her şema alanının değerini bulur.

    Parametreler:
        metin   -> OCR'ın okuduğu ham metin (çok satırlı)
        alanlar -> şema alanları: [{"alan_adi", "veri_tipi", "anahtar_kelimeler"}, ...]
    Döndürür:
        {alan_adi: {"deger": "..." veya None, "guven": 0.0-1.0, "yontem": "..."}}
    """
    ham_satirlar = [s.strip() for s in (metin or "").splitlines() if s.strip()]
    satirlar = [sadelestir(s) for s in ham_satirlar]  # karşılaştırma için sade hâli
    sade_metin = "\n".join(satirlar)

    sonuc = {}
    for alan in alanlar:
        deger, guven = _anahtar_kelime_ile(satirlar, alan)
        yontem = "anahtar_kelime" if deger else None
        if deger is None:
            deger, guven, yontem = _kalip_ile(sade_metin, satirlar, ham_satirlar, alan)
        sonuc[alan["alan_adi"]] = {"deger": deger, "guven": guven, "yontem": yontem}

    # Özel durum (KDV oranı): Fişteki TÜM oranlara bakılır.
    #   - Farklı oranlı ürünler varsa (ör. ekmek %1, deterjan %20) tek bir "KDV oranı" yoktur;
    #     yanlış oranla hesap yapılmasın diye boş bırakılır.
    #   - Hepsi aynıysa ve anahtar kelimeyle bulunamadıysa (OCR "%" işaretini kaçırmış olabilir)
    #     o oran kullanılır.
    if "kdv_orani" in sonuc:
        oranlar = set(kdv_oranlari_bul(sade_metin))
        if len(oranlar) > 1:
            sonuc["kdv_orani"] = {"deger": None, "guven": 0.0, "yontem": "karisik_oran"}
        elif len(oranlar) == 1 and sonuc["kdv_orani"]["deger"] is None:
            sonuc["kdv_orani"] = {"deger": str(oranlar.pop()), "guven": GUVEN_KALIP, "yontem": "kalip"}
    return sonuc
