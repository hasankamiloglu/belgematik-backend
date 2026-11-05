"""
dogrulayici.py - Çıkarılan değerleri kurallara göre doğrular.

İKİ SEVİYE DOĞRULAMA:
    1) ALAN KURALLARI (her alan tek başına)          -> alan_dogrula()
       a) Zorunlu alan boş mu?
       b) Veri tipine uygun mu? (tarih gerçek bir tarih mi, para pozitif mi?)
       c) Şemadaki regex kuralına uyuyor mu? (ör. ^[0-9]{10,11}$)
       d) Alana özel kural: vergi no kontrol hanesi, e-posta, telefon, KDV oranı, gelecek tarih

    2) İŞ KURALLARI (alanlar birbiriyle tutarlı mı?)  -> is_kurallari()
       - KDV, toplamdan küçük olmalı
       - KDV tutarı, oran ile hesaplanan tutara eşit olmalı
       - Matrah + KDV = Toplam (faturada)

Neden ikisi de? Her alan tek tek doğru görünse bile birbirleriyle çelişebilir:
OCR "247,50" yerine "347,50" okursa toplam yine geçerli bir para değeridir,
ama KDV ile tutmaz. Bu hatayı sadece iş kuralı yakalar.
"""

import re
from datetime import date, timedelta
from decimal import Decimal

from app.services.extraction.metin_araclari import para_coz, tarih_coz
from app.services.validation.kimlik_no import vergi_no_gecerli_mi

# Türkiye'de kullanılan / kullanılmış KDV oranları (yüzde)
GECERLI_KDV_ORANLARI = {0, 1, 8, 10, 18, 20}
EMAIL_KALIBI = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
TELEFON_KALIBI = re.compile(r"^0[2-5]\d{9}$")  # 0 + 10 hane: 05321234567
# Kuruş farkı toleransı: OCR ve yuvarlama yüzünden 1-2 kuruş fark olabilir
KURUS_TOLERANSI = Decimal("0.05")


# =================================================================== 1) ALAN
def alan_dogrula(alan, deger, bugun=None):
    """
    Tek bir alanı doğrular.

    Parametreler:
        alan  -> şema alanı: {"alan_adi", "veri_tipi", "zorunlu_mu", "dogrulama_kurali"}
        deger -> bulunan değer (metin) veya None
        bugun -> testlerde sabit tarih vermek için (verilmezse bugünün tarihi)
    Döndürür: (gecerli_mi, hata_mesaji)   ör. (False, "Zorunlu alan bulunamadı.")
    """
    bugun = bugun or date.today()
    ad, tip = alan["alan_adi"], alan["veri_tipi"]

    # a) Zorunlu alan
    if deger in (None, ""):
        return (False, "Zorunlu alan bulunamadı.") if alan.get("zorunlu_mu") else (True, None)

    # b) Veri tipi
    if tip == "para":
        tutar = para_coz(deger)
        if tutar is None:
            return False, "Geçerli bir para tutarı değil."
        if tutar <= 0:
            return False, "Tutar sıfırdan büyük olmalı."
    elif tip == "tarih":
        tarih = tarih_coz(deger)
        if tarih is None:
            return False, "Geçerli bir tarih değil."
        if tarih > bugun + timedelta(days=1):
            return False, "Tarih gelecekte olamaz."
        if tarih < date(2000, 1, 1):
            return False, "Tarih çok eski (2000 öncesi)."
    elif tip == "sayi":
        if not re.fullmatch(r"-?\d+([.,]\d+)?", str(deger)):
            return False, "Sayı değil."

    # c) Şemadaki regex kuralı (kullanıcı kendi şemasında yazabilir)
    kural = alan.get("dogrulama_kurali")
    if kural and not re.fullmatch(kural, str(deger)):
        return False, f"Beklenen biçime uymuyor ({kural})."

    # d) Alana özel kurallar
    if ad == "vergi_no" and not vergi_no_gecerli_mi(str(deger)):
        return False, "Vergi numarasının kontrol hanesi tutmuyor (yanlış okunmuş olabilir)."
    if ad == "email" and not EMAIL_KALIBI.match(str(deger)):
        return False, "Geçerli bir e-posta adresi değil."
    if ad == "telefon" and not TELEFON_KALIBI.match(str(deger)):
        return False, "Geçerli bir telefon numarası değil."
    if ad == "kdv_orani" and int(float(str(deger).replace(",", "."))) not in GECERLI_KDV_ORANLARI:
        return False, f"KDV oranı %{deger} Türkiye'de kullanılmıyor."

    return True, None


# ============================================================== 2) İŞ KURALI
def is_kurallari(degerler):
    """
    Alanlar arası tutarlılık kuralları. Sadece gerekli alanlar BULUNDUYSA uygulanır.

    Parametre:
        degerler -> {alan_adi: deger}  ör. {"kdv_tutari": "41.25", "toplam_tutar": "247.50"}
    Döndürür:
        [{"kural": "...", "gecerli": True/False, "mesaj": "..."}, ...]
    """
    kdv = para_coz(degerler.get("kdv_tutari")) if degerler.get("kdv_tutari") else None
    toplam = para_coz(degerler.get("toplam_tutar")) if degerler.get("toplam_tutar") else None
    matrah = para_coz(degerler.get("matrah")) if degerler.get("matrah") else None
    oran = degerler.get("kdv_orani")
    oran = Decimal(str(oran).replace(",", ".")) if oran not in (None, "") else None

    sonuclar = []

    def ekle(kural, gecerli, mesaj):
        sonuclar.append({"kural": kural, "gecerli": gecerli, "mesaj": mesaj})

    # Kural 1: KDV toplamdan küçük olmalı
    if kdv is not None and toplam is not None:
        ekle("KDV < Toplam", kdv < toplam,
             "Uygun." if kdv < toplam else f"KDV ({kdv}) toplamdan ({toplam}) büyük olamaz.")

    # Kural 2: KDV-dahil toplamdan hesaplanan KDV = okunan KDV
    #   KDV dahil fiyattan KDV:  toplam × oran / (100 + oran)
    #   Örnek: 120 TL, %20 -> 120 × 20 / 120 = 20 TL
    if kdv is not None and toplam is not None and oran is not None and matrah is None:
        beklenen = (toplam * oran / (100 + oran)).quantize(Decimal("0.01"))
        fark = abs(beklenen - kdv)
        ekle(f"KDV = Toplam × %{oran} / (100 + {oran})", fark <= KURUS_TOLERANSI,
             "Uygun." if fark <= KURUS_TOLERANSI
             else f"Hesaplanan KDV {beklenen}, okunan {kdv} (fark {fark}).")

    # Kural 3: Matrah + KDV = Toplam (faturalarda)
    if matrah is not None and kdv is not None and toplam is not None:
        fark = abs(matrah + kdv - toplam)
        ekle("Matrah + KDV = Toplam", fark <= KURUS_TOLERANSI,
             "Uygun." if fark <= KURUS_TOLERANSI
             else f"{matrah} + {kdv} = {matrah + kdv}, ama toplam {toplam} (fark {fark}).")

    return sonuclar


# ================================================================ HEPSİ
def dogrula(alanlar, bulunanlar, bugun=None):
    """
    Bir çıkarımın tümünü doğrular.

    Parametreler:
        alanlar    -> şema alanları listesi
        bulunanlar -> alanlari_esle() sonucu: {alan_adi: {"deger", "guven", ...}}
    Döndürür:
        (alan_sonuclari, kural_sonuclari, hepsi_gecerli_mi)
        alan_sonuclari -> {alan_adi: {"gecerli": bool, "hata_mesaji": str|None}}
    """
    alan_sonuclari = {}
    for alan in alanlar:
        deger = bulunanlar.get(alan["alan_adi"], {}).get("deger")
        gecerli, mesaj = alan_dogrula(alan, deger, bugun)
        alan_sonuclari[alan["alan_adi"]] = {"gecerli": gecerli, "hata_mesaji": mesaj}

    kural_sonuclari = is_kurallari(
        {ad: b.get("deger") for ad, b in bulunanlar.items() if alan_sonuclari.get(ad, {}).get("gecerli")}
    )
    hepsi = all(a["gecerli"] for a in alan_sonuclari.values()) and all(k["gecerli"] for k in kural_sonuclari)
    return alan_sonuclari, kural_sonuclari, hepsi
