"""
test_harici_api.py - Harici OCR API (OCR.space) entegrasyonu testleri (Hafta 9).

Bu testler İNTERNETE ÇIKMAZ. requests.post yerine SAHTE bir fonksiyon koyarız
(monkeypatch) ve servisin vereceği cevapları biz üretiriz: başarılı cevap,
yanlış anahtar, hız sınırı, zaman aşımı, sunucu hatası, bozuk cevap...
Böylece her hata durumunu gerçek kotayı harcamadan deneyebiliriz.
"""

import subprocess
from pathlib import Path

import pytest
import requests
from PIL import Image

from app.services.ocr import harici_api, motor_secici, tesseract

KOK = Path(__file__).resolve().parent.parent

BASARILI_GOVDE = {
    "ParsedResults": [{"ParsedText": "ORNEK MARKET A.S.\r\nTOPLAM 120,00\r\n", "FileParseExitCode": 1}],
    "OCRExitCode": 1,
    "IsErroredOnProcessing": False,
    "ErrorMessage": None,
}


class SahteCevap:
    """requests.Response yerine geçen basit nesne."""

    def __init__(self, durum_kodu=200, govde=None, metin=None):
        self.status_code = durum_kodu
        self._govde = govde
        self.text = metin if metin is not None else str(govde)

    def json(self):
        if self._govde is None:
            raise ValueError("JSON değil")
        return self._govde


class SahteServis:
    """
    Sırayla verilen cevapları döndüren sahte requests.post.
    Listedeki eleman bir istisna (exception) ise fırlatılır (ör. zaman aşımı).
    Gelen istekleri de saklar: hangi başlık, hangi zaman aşımı gönderildi?
    """

    def __init__(self, *cevaplar):
        self.cevaplar = list(cevaplar)
        self.istekler = []

    def __call__(self, adres, **kwargs):
        self.istekler.append({"adres": adres, **kwargs})
        cevap = self.cevaplar.pop(0) if len(self.cevaplar) > 1 else self.cevaplar[0]
        if isinstance(cevap, Exception):
            raise cevap
        return cevap


@pytest.fixture
def gorsel(tmp_path):
    yol = tmp_path / "fis.png"
    Image.new("L", (400, 200), 255).save(yol)
    return str(yol)


@pytest.fixture(autouse=True)
def ortam(monkeypatch):
    """Her test temiz başlar: sahte anahtar, yeni hız sınırlayıcı."""
    monkeypatch.setenv("OCR_API_ANAHTARI", "TEST_ANAHTARI_12345678")
    monkeypatch.setenv("OCR_API_DAKIKA_SINIRI", "100")
    monkeypatch.setattr(harici_api, "_sinirlayici", None)


def _servis(monkeypatch, *cevaplar):
    servis = SahteServis(*cevaplar)
    monkeypatch.setattr(harici_api.requests, "post", servis)
    return servis


def _oku(gorsel, beklemeler=None):
    """Testte gerçekten beklememek için bekleme süreleri listeye yazılır."""
    beklemeler = [] if beklemeler is None else beklemeler
    return harici_api.metin_oku(gorsel, bekle=beklemeler.append)


# ======================================================== BAŞARILI ÇAĞRI
def test_basarili_cevap_ayristirilir(monkeypatch, gorsel):
    servis = _servis(monkeypatch, SahteCevap(200, BASARILI_GOVDE))
    sonuc = _oku(gorsel)

    assert sonuc["motor"] == "ocr_space"
    assert sonuc["metin"] == "ORNEK MARKET A.S.\nTOPLAM 120,00"  # \r\n -> \n, boşluklar kırpıldı
    assert sonuc["deneme"] == 1 and 0 < sonuc["guven"] <= 1

    istek = servis.istekler[0]
    assert istek["adres"] == harici_api.API_ADRESI
    assert istek["headers"]["apikey"] == "TEST_ANAHTARI_12345678"  # anahtar başlıkta gider
    assert istek["timeout"] == (harici_api.BAGLANTI_SURESI, harici_api.OKUMA_SURESI)
    assert istek["data"]["language"] == "tur"
    assert istek["data"]["isTable"] == "true"  # fiş satırları bölünmeden gelsin


def test_cok_sayfali_cevap_birlestirilir():
    govde = {"ParsedResults": [{"ParsedText": "SAYFA 1"}, {"ParsedText": "SAYFA 2"}],
             "IsErroredOnProcessing": False}
    assert harici_api.yaniti_cozumle(govde) == "SAYFA 1\nSAYFA 2"


# ======================================================== KİMLİK / ANAHTAR
def test_anahtar_yoksa_istek_gonderilmez(monkeypatch, gorsel):
    monkeypatch.delenv("OCR_API_ANAHTARI")
    servis = _servis(monkeypatch, SahteCevap(200, BASARILI_GOVDE))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "anahtar_yok"
    assert servis.istekler == []


@pytest.mark.parametrize("kod", [401, 403])
def test_yanlis_anahtar_tekrar_denenmez(monkeypatch, gorsel, kod):
    servis = _servis(monkeypatch, SahteCevap(kod, metin="The API key is invalid"))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "kimlik" and h.value.http_kodu == kod
    assert len(servis.istekler) == 1  # anahtar yanlışsa tekrar denemek boşuna


def test_govdede_gelen_anahtar_hatasi_taninir(monkeypatch, gorsel):
    """OCR.space bazen HTTP 200 ile hata döndürür; hata bilgisi gövdededir."""
    govde = {"IsErroredOnProcessing": True, "ErrorMessage": ["The API key is invalid or not provided"]}
    _servis(monkeypatch, SahteCevap(200, govde))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "kimlik"


def test_maskeli_anahtar_gercek_anahtari_gostermez():
    maske = harici_api.maskeli_anahtar()
    assert maske == "TE****5678"
    assert "TEST_ANAHTARI" not in maske


# ======================================================== HIZ SINIRI
def test_servisin_hiz_siniri_429_tekrar_denenmez(monkeypatch, gorsel):
    servis = _servis(monkeypatch, SahteCevap(429, metin="Too many requests"))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "hiz_siniri"
    assert len(servis.istekler) == 1


def test_kendi_hiz_sinirimiz_dolunca_apiye_gidilmez(monkeypatch, gorsel):
    monkeypatch.setenv("OCR_API_DAKIKA_SINIRI", "2")
    servis = _servis(monkeypatch, SahteCevap(200, BASARILI_GOVDE))
    _oku(gorsel)
    _oku(gorsel)
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)  # 3. çağrı: sınır 2
    assert h.value.tur == "hiz_siniri"
    assert len(servis.istekler) == 2  # 3. istek servise HİÇ gitmedi


def test_hiz_sinirlayici_pencere_gecince_tekrar_izin_verir():
    s = harici_api.HizSinirlayici(en_fazla=2, pencere_sn=60)
    assert s.izin_var_mi(simdi=0) and s.izin_var_mi(simdi=10)
    assert not s.izin_var_mi(simdi=30)   # 60 sn içinde 3. çağrı
    assert s.izin_var_mi(simdi=61)       # ilk çağrı pencereden çıktı


# ======================================================== ZAMAN AŞIMI / TEKRAR
def test_zaman_asimindan_sonra_tekrar_denenir_ve_basarir(monkeypatch, gorsel):
    servis = _servis(monkeypatch, requests.Timeout(), requests.Timeout(), SahteCevap(200, BASARILI_GOVDE))
    beklemeler = []
    sonuc = _oku(gorsel, beklemeler)
    assert sonuc["deneme"] == 3
    assert len(servis.istekler) == 3
    assert beklemeler == [1.0, 2.0]  # üstel geri çekilme: 1 sn, 2 sn


def test_hep_zaman_asimi_olursa_3_denemeden_sonra_vazgecilir(monkeypatch, gorsel):
    servis = _servis(monkeypatch, requests.Timeout())
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "zaman_asimi" and h.value.deneme == 3
    assert len(servis.istekler) == harici_api.EN_FAZLA_DENEME


def test_baglanti_hatasi_tekrar_denenir(monkeypatch, gorsel):
    servis = _servis(monkeypatch, requests.ConnectionError(), SahteCevap(200, BASARILI_GOVDE))
    assert _oku(gorsel)["deneme"] == 2
    assert len(servis.istekler) == 2


def test_sunucu_hatasi_5xx_tekrar_denenir(monkeypatch, gorsel):
    _servis(monkeypatch, SahteCevap(503, metin="Service Unavailable"), SahteCevap(200, BASARILI_GOVDE))
    assert _oku(gorsel)["deneme"] == 2


# ======================================================== BOZUK CEVAP
def test_json_olmayan_cevap_yanit_hatasidir(monkeypatch, gorsel):
    _servis(monkeypatch, SahteCevap(200, None, metin="<html>Bakımdayız</html>"))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "yanit"


def test_bos_sonuc_yanit_hatasidir(monkeypatch, gorsel):
    _servis(monkeypatch, SahteCevap(200, {"ParsedResults": [], "IsErroredOnProcessing": False}))
    with pytest.raises(harici_api.ApiHatasi) as h:
        _oku(gorsel)
    assert h.value.tur == "yanit"


# ======================================================== GÖRSEL BOYUTU
def test_buyuk_gorsel_1mb_altina_indirilir(tmp_path):
    import os

    yol = tmp_path / "buyuk.png"
    # Rastgele gürültü JPEG ile iyi sıkışmaz -> küçültme gerçekten devreye girer
    Image.frombytes("L", (3000, 3000), os.urandom(3000 * 3000)).save(yol)
    veri = harici_api._gorseli_hazirla(str(yol))
    assert len(veri) <= harici_api.EN_BUYUK_DOSYA
    assert veri[:2] == b"\xff\xd8"  # JPEG dosyası


# ======================================================== MOTOR SEÇİCİ (YEDEK)
@pytest.fixture
def sahte_tesseract(monkeypatch):
    monkeypatch.setattr(tesseract, "metin_oku",
                        lambda yol: {"metin": "TESSERACT METNI", "guven": 0.7, "motor": "tesseract"})
    monkeypatch.setattr(motor_secici, "_gunluge_yaz", lambda *a, **k: None)  # DB'ye yazma


def test_otomatik_modda_api_hata_verirse_tesseract_yedek_olur(monkeypatch, gorsel, sahte_tesseract):
    monkeypatch.setenv("OCR_MOTORU", "otomatik")
    _servis(monkeypatch, SahteCevap(403, metin="invalid key"))
    sonuc = motor_secici.metin_oku(gorsel)
    assert sonuc["motor"] == "tesseract"
    assert "Tesseract ile okundu" in sonuc["not"]


def test_otomatik_modda_api_calisirsa_api_kullanilir(monkeypatch, gorsel, sahte_tesseract):
    monkeypatch.setenv("OCR_MOTORU", "otomatik")
    _servis(monkeypatch, SahteCevap(200, BASARILI_GOVDE))
    sonuc = motor_secici.metin_oku(gorsel)
    assert sonuc["motor"] == "ocr_space" and sonuc["not"] is None


def test_otomatik_modda_anahtar_yoksa_dogrudan_tesseract(monkeypatch, gorsel, sahte_tesseract):
    monkeypatch.setenv("OCR_MOTORU", "otomatik")
    monkeypatch.delenv("OCR_API_ANAHTARI")
    servis = _servis(monkeypatch, SahteCevap(200, BASARILI_GOVDE))
    assert motor_secici.metin_oku(gorsel)["motor"] == "tesseract"
    assert servis.istekler == []


def test_api_modunda_hata_kullaniciya_doner(monkeypatch, gorsel, sahte_tesseract):
    monkeypatch.setenv("OCR_MOTORU", "api")
    _servis(monkeypatch, SahteCevap(503, metin="down"))
    with pytest.raises(harici_api.ApiHatasi):
        motor_secici.metin_oku(gorsel)


# ======================================================== ANAHTAR DEPODA DEĞİL
def test_env_dosyasi_gitignore_icinde():
    assert ".env" in (KOK / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_env_example_da_gercek_anahtar_yok():
    for satir in (KOK / ".env.example").read_text(encoding="utf-8").splitlines():
        if satir.startswith("OCR_API_ANAHTARI="):
            assert satir == "OCR_API_ANAHTARI=", "Örnek dosyada anahtar boş kalmalı"


def test_depoda_env_dosyasi_takip_edilmiyor():
    """Git'in takip ettiği dosyalar arasında .env olmamalı (git yoksa atlanır)."""
    try:
        dosyalar = subprocess.run(["git", "ls-files"], cwd=KOK, capture_output=True,
                                  text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git bulunamadı")
    assert ".env" not in dosyalar
