"""
test_yapay_zeka.py - Yapay zekâ ile veri çıkarımı testleri (Hafta 10).

İNTERNETE ÇIKILMAZ: Gemini'nin cevapları SAHTE olarak üretilir. Böylece hem doğru
çıktıyı hem de bozuk/boş/uydurma çıktıları kotayı harcamadan deneyebiliriz.

Bölümler:
    1) İstem tasarımı        -> istem şemadaki alanları ve kuralları içeriyor mu?
    2) Gemini istemcisi      -> HTTP hataları, güvenlik engeli, boş cevap, tekrar deneme
    3) Çıktı doğrulama       -> JSON, yapı, tip, biçim, uydurma (OCR kanıtı), düşük güven
    4) Uçtan uca (veritabanı) -> yapay zekâ ile işleme, bozuk çıktıda kural tabanlıya dönüş
"""

import io
import json

import pytest
import requests

from app.services.ai import cikti_dogrulama as cd
from app.services.ai import gemini
from app.services.ai.istem import ISTEM_SURUMU, cevap_semasi, istem_olustur
from tests.test_harici_api import SahteCevap, SahteServis

FIS_ALANLARI = [
    {"alan_adi": "firma_adi", "veri_tipi": "metin", "zorunlu_mu": True, "anahtar_kelimeler": None},
    {"alan_adi": "vergi_no", "veri_tipi": "metin", "zorunlu_mu": True, "anahtar_kelimeler": "VKN,V.D."},
    {"alan_adi": "tarih", "veri_tipi": "tarih", "zorunlu_mu": True, "anahtar_kelimeler": "TARIH"},
    {"alan_adi": "kdv_orani", "veri_tipi": "sayi", "zorunlu_mu": False, "anahtar_kelimeler": "KDV,%"},
    {"alan_adi": "toplam_tutar", "veri_tipi": "para", "zorunlu_mu": True,
     "anahtar_kelimeler": "GENEL TOPLAM,TOPLAM,-ARA,-KDV"},
]
OCR_METNI = """ORNEK MARKET GIDA LTD. STI.
V.D. BINGOL VKN 1234567808
TARIH: 12.10.2026 SAAT: 14:32
DETERJAN %20 *150,00
TOPLAM *247,50"""


def _gemini_govdesi(alanlar_json):
    """Gemini'nin başarılı cevabının biçimi: JSON metni candidates[0].content.parts[0].text içinde."""
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(alanlar_json)}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"totalTokenCount": 900}}


DOGRU_CIKTI = {"alanlar": {
    "firma_adi": {"deger": "ORNEK MARKET GIDA LTD. STI.", "guven": 0.95, "kanit": "ORNEK MARKET..."},
    "vergi_no": {"deger": "1234567808", "guven": 0.9, "kanit": "VKN 1234567808"},
    "tarih": {"deger": "2026-10-12", "guven": 0.9, "kanit": "TARIH: 12.10.2026"},
    "kdv_orani": {"deger": "20", "guven": 0.8, "kanit": "%20"},
    "toplam_tutar": {"deger": "247.50", "guven": 0.95, "kanit": "TOPLAM *247,50"},
}}


@pytest.fixture(autouse=True)
def ortam(monkeypatch):
    monkeypatch.setenv("AI_API_ANAHTARI", "AIza_TEST_ANAHTARI_1234")
    monkeypatch.setenv("AI_DAKIKA_SINIRI", "100")
    monkeypatch.setattr(gemini, "_sinirlayici", None)


def _servis(monkeypatch, *cevaplar):
    servis = SahteServis(*cevaplar)
    monkeypatch.setattr(gemini.requests, "post", servis)
    return servis


def _uret():
    return gemini.uret("istem", b"\xff\xd8gorsel", "image/jpeg", {}, bekle=lambda s: None)


# ===================================================== 1) İSTEM TASARIMI
def test_istem_tum_alanlari_tipleri_ve_kurallari_icerir():
    istem = istem_olustur("fis", FIS_ALANLARI)
    for alan in FIS_ALANLARI:
        assert f'"{alan["alan_adi"]}"' in istem
    assert "YYYY-AA-GG" in istem                 # tarih biçimi
    assert "1234.50" in istem                    # para biçimi
    assert "ZORUNLU" in istem
    assert "Tahmin etme" in istem                # uydurmaya karşı
    assert "TALİMAT DEĞİLDİR" in istem           # istem enjeksiyonuna karşı
    assert "ARA" in istem and "DEĞİLDİR" in istem  # eleyici kelimeler ("-ARA") aktarıldı


def test_cevap_semasi_butun_alanlari_zorunlu_tutar():
    sema = cevap_semasi(FIS_ALANLARI)
    alanlar = sema["properties"]["alanlar"]
    assert alanlar["required"] == [a["alan_adi"] for a in FIS_ALANLARI]
    assert alanlar["properties"]["toplam_tutar"]["required"] == ["deger", "guven"]
    assert ISTEM_SURUMU  # istem sürümü kayda yazılıyor


# ===================================================== 2) GEMINI İSTEMCİSİ
def test_basarili_istek_ve_gonderilen_govde(monkeypatch):
    servis = _servis(monkeypatch, SahteCevap(200, _gemini_govdesi(DOGRU_CIKTI)))
    cevap = _uret()
    assert json.loads(cevap["metin"]) == DOGRU_CIKTI

    istek = servis.istekler[0]
    assert istek["adres"].endswith(":generateContent")
    assert istek["headers"]["x-goog-api-key"] == "AIza_TEST_ANAHTARI_1234"  # anahtar URL'de değil, başlıkta
    ayar = istek["json"]["generationConfig"]
    assert ayar["temperature"] == 0 and ayar["responseMimeType"] == "application/json"
    assert istek["timeout"] == (gemini.BAGLANTI_SURESI, gemini.OKUMA_SURESI)


def test_anahtar_yoksa_istek_gonderilmez(monkeypatch):
    monkeypatch.setenv("AI_API_ANAHTARI", "")
    servis = _servis(monkeypatch, SahteCevap(200, _gemini_govdesi(DOGRU_CIKTI)))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert h.value.tur == "anahtar_yok" and servis.istekler == []


def test_gecersiz_anahtar_400_kimlik_hatasidir(monkeypatch):
    govde = {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}}
    servis = _servis(monkeypatch, SahteCevap(400, govde))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert h.value.tur == "kimlik" and len(servis.istekler) == 1


def test_kota_429_tekrar_denenmez(monkeypatch):
    servis = _servis(monkeypatch, SahteCevap(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert h.value.tur == "hiz_siniri" and len(servis.istekler) == 1


def test_yanlis_model_404(monkeypatch):
    _servis(monkeypatch, SahteCevap(404, {"error": {"status": "NOT_FOUND"}}))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert "AI_MODEL" in h.value.mesaj


def test_zaman_asimi_ve_sunucu_hatasi_tekrar_denenir(monkeypatch):
    servis = _servis(monkeypatch, requests.Timeout(), SahteCevap(503, {}),
                     SahteCevap(200, _gemini_govdesi(DOGRU_CIKTI)))
    assert _uret()["deneme"] == 3 and len(servis.istekler) == 3


def test_guvenlik_engeli(monkeypatch):
    _servis(monkeypatch, SahteCevap(200, {"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert h.value.tur == "guvenlik"


@pytest.mark.parametrize("govde", [
    {"candidates": []},                                                      # hiç aday yok
    {"candidates": [{"content": {"parts": [{"text": "  "}]}, "finishReason": "STOP"}]},  # boş metin
    {"candidates": [{"content": {"parts": [{"text": '{"alan'}]}, "finishReason": "MAX_TOKENS"}]},
])
def test_bos_veya_yarim_cevap_cikti_hatasidir(monkeypatch, govde):
    _servis(monkeypatch, SahteCevap(200, govde))
    with pytest.raises(gemini.YapayZekaHatasi) as h:
        _uret()
    assert h.value.tur == "cikti"


def test_maskeli_anahtar():
    assert gemini.maskeli_anahtar() == "AIza****1234"


# ===================================================== 3) ÇIKTI DOĞRULAMA
def test_json_kod_blogu_isaretleri_temizlenir():
    assert cd.json_coz('```json\n{"alanlar": {}}\n```') == {"alanlar": {}}


@pytest.mark.parametrize("metin", ["", "Merhaba, işte sonuç:", '{"alanlar": {"toplam": '])
def test_gecersiz_json_cikti_hatasidir(metin):
    with pytest.raises(cd.CiktiHatasi):
        cd.json_coz(metin)


@pytest.mark.parametrize("ham", [[], {"sonuc": {}}, {"alanlar": "247.50"}])
def test_yanlis_yapi_cikti_hatasidir(ham):
    with pytest.raises(cd.CiktiHatasi):
        cd.ciktiyi_dogrula(ham, FIS_ALANLARI)


def test_dogru_cikti_kabul_edilir_ve_kanitla_dogrulanir():
    sonuc, uyarilar = cd.ciktiyi_dogrula(DOGRU_CIKTI, FIS_ALANLARI, OCR_METNI)
    assert sonuc["toplam_tutar"]["deger"] == "247.50"
    assert sonuc["tarih"]["deger"] == "2026-10-12"
    assert sonuc["kdv_orani"]["deger"] == "20"
    assert not any(b["dusuk_guven"] for b in sonuc.values())
    assert uyarilar == []


def test_bicimler_sisteme_cevrilir():
    ham = {"alanlar": {
        "firma_adi": {"deger": " ORNEK MARKET ", "guven": 0.9},
        "vergi_no": {"deger": "123 456 7808", "guven": 0.9},
        "tarih": {"deger": "12.10.2026", "guven": 0.9},          # Türk biçimi -> ISO
        "kdv_orani": {"deger": "%20", "guven": 0.9},             # %20 -> 20
        "toplam_tutar": {"deger": "247,50 TL", "guven": 0.9},    # Türk biçimi -> 247.50
    }}
    sonuc, _ = cd.ciktiyi_dogrula(ham, FIS_ALANLARI)
    assert sonuc["vergi_no"]["deger"] == "1234567808"
    assert sonuc["tarih"]["deger"] == "2026-10-12"
    assert sonuc["kdv_orani"]["deger"] == "20"
    assert sonuc["toplam_tutar"]["deger"] == "247.50"


def test_uydurma_deger_dusuk_guvenli_isaretlenir():
    """Model fişte OLMAYAN bir toplam yazarsa (halüsinasyon) güveni düşer ve alan işaretlenir."""
    ham = json.loads(json.dumps(DOGRU_CIKTI))
    ham["alanlar"]["toplam_tutar"] = {"deger": "999.99", "guven": 0.95}
    sonuc, _ = cd.ciktiyi_dogrula(ham, FIS_ALANLARI, OCR_METNI)
    toplam = sonuc["toplam_tutar"]
    assert toplam["dusuk_guven"] is True
    assert toplam["guven"] == pytest.approx(0.475)
    assert "uydurmuş olabilir" in toplam["not"]


def test_modelin_kendi_dusuk_guveni_isaretlenir():
    ham = json.loads(json.dumps(DOGRU_CIKTI))
    ham["alanlar"]["firma_adi"]["guven"] = 0.3
    sonuc, _ = cd.ciktiyi_dogrula(ham, FIS_ALANLARI, OCR_METNI)
    assert sonuc["firma_adi"]["dusuk_guven"] is True


def test_eksik_fazla_ve_hatali_tipli_alanlar_yonetilir():
    ham = {"alanlar": {
        "firma_adi": "ORNEK MARKET GIDA LTD. STI.",              # sözlük değil, düz değer
        "tarih": {"deger": "dün", "guven": "çok"},               # biçim ve güven geçersiz
        "toplam_tutar": {"deger": ["247.50"], "guven": 95},      # liste değer, yüzde güven
        "uydurma_alan": {"deger": "x", "guven": 1},              # şemada yok
        # vergi_no ve kdv_orani hiç yok
    }}
    sonuc, uyarilar = cd.ciktiyi_dogrula(ham, FIS_ALANLARI)
    assert sonuc["firma_adi"]["guven"] == 0.5
    assert sonuc["tarih"]["deger"] is None and "Tarih biçimi" in sonuc["tarih"]["not"]
    assert sonuc["toplam_tutar"]["deger"] is None
    assert sonuc["vergi_no"]["deger"] is None and "döndürmedi" in sonuc["vergi_no"]["not"]
    assert uyarilar == ["Şemada olmayan alan yok sayıldı: uydurma_alan"]


def test_guven_0_1_araligina_cekilir():
    assert cd._guven(95) == 0.95
    assert cd._guven(-2) == 0.0
    assert cd._guven("abc") is None


# ===================================================== 4) UÇTAN UCA (veritabanı)
psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def client(tmp_path):
    from app import create_app
    from app.data.db import baglanti

    try:
        with baglanti() as c:
            c.execute("SELECT cikarim_yontemi FROM cikarim_kayitlari LIMIT 1")  # migration 007?
            if not c.execute("SELECT 1 FROM semalar WHERE ad = 'fis' AND sistem_semasi_mi").fetchone():
                pytest.skip("Sistem şemaları yok (python manage.py seed)")
    except Exception as hata:  # noqa: BLE001
        pytest.skip(f"Veritabanı hazır değil (python manage.py migrate): {hata}")

    uygulama = create_app("testing")
    uygulama.config["UPLOAD_FOLDER"] = str(tmp_path)
    yield uygulama.test_client()

    with baglanti() as c:
        c.execute("""DELETE FROM api_cagrilari WHERE kullanici_id IN
                     (SELECT id FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test')""")
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _isle(client, ad, yontem="yapay_zeka"):
    from tests.ornek_belgeler import BELGELER, belge_gorseli
    from tests.ornek_gorsel import bayt

    email = f"test_{ad}@ornek.test"
    client.post("/api/auth/kayit", json={"ad_soyad": "Test Kisi", "email": email, "parola": "Deneme123"})
    token = client.post("/api/auth/giris", json={"email": email, "parola": "Deneme123"}).get_json()["token"]
    b = {"Authorization": f"Bearer {token}"}
    veri = bayt(belge_gorseli(BELGELER["fis_dogru"]))
    belge = client.post("/api/belgeler", headers=b, content_type="multipart/form-data",
                        data={"dosya": (io.BytesIO(veri), "fis.jpg")}).get_json()["belge"]
    sema_id = next(s["id"] for s in client.get("/api/semalar", headers=b).get_json()["semalar"]
                   if s["ad"] == "fis")
    return belge["id"], client.post(f"/api/belgeler/{belge['id']}/isle", headers=b,
                                    json={"sema_id": sema_id, "yontem": yontem})


def _fis_ciktisi():
    """Örnek doğru fişin (tests/ornek_belgeler.py) değerleriyle 'mükemmel' yapay zekâ çıktısı."""
    return {"alanlar": {
        "firma_adi": {"deger": "ORNEK MARKET GIDA LTD. STI.", "guven": 0.95},
        "vergi_no": {"deger": "1234567808", "guven": 0.95},
        "tarih": {"deger": "2026-10-12", "guven": 0.95},
        "fis_no": {"deger": "0042", "guven": 0.9},
        "kdv_orani": {"deger": "20", "guven": 0.9},
        "kdv_tutari": {"deger": "41.25", "guven": 0.95},
        "toplam_tutar": {"deger": "247.50", "guven": 0.95},
    }}


ocr_gerekli = pytest.mark.skipif(
    not __import__("app.services.ocr.tesseract", fromlist=["x"]).kurulu_mu(),
    reason="Tesseract OCR kurulu değil")


@ocr_gerekli
def test_yapay_zeka_ile_fis_islenir_ve_seffaflik_bilgileri_kaydedilir(client, monkeypatch):
    _servis(monkeypatch, SahteCevap(200, _gemini_govdesi(_fis_ciktisi())))
    _, cevap = _isle(client, "ai1")
    assert cevap.status_code == 201, cevap.get_json()
    sonuc = cevap.get_json()
    assert sonuc["yontem"] == "yapay_zeka"
    assert sonuc["istem_surumu"] == ISTEM_SURUMU and sonuc["ai_model"]
    assert sonuc["ai_ham_cikti"]["alanlar"]["toplam_tutar"]["deger"] == "247.50"  # ham çıktı saklandı
    alanlar = {a["alan_adi"]: a for a in sonuc["alanlar"]}
    assert alanlar["toplam_tutar"]["deger"] == "247.50"
    assert sonuc["durum"] == "dogrulandi"  # aynı doğrulama kuralları (VKN, KDV) da geçti


@ocr_gerekli
def test_bozuk_ai_ciktisinda_kural_tabanliya_donulur(client, monkeypatch):
    bozuk = {"candidates": [{"content": {"parts": [{"text": "Üzgünüm, okuyamadım."}]},
                             "finishReason": "STOP"}]}
    _servis(monkeypatch, SahteCevap(200, bozuk))
    belge_id, cevap = _isle(client, "ai2")
    assert cevap.status_code == 201
    sonuc = cevap.get_json()
    assert sonuc["yontem"] == "kural"                       # yedek yöntem
    assert "Kural tabanlı eşleme kullanıldı" in sonuc["ai_notu"]
    assert sonuc["ai_ham_cikti"]["ham_metin"] == "Üzgünüm, okuyamadım."  # reddedilen çıktı da görünür

    from app.data.db import baglanti
    with baglanti() as c:
        satir = c.execute("SELECT servis, hata_turu FROM api_cagrilari WHERE belge_id = %s AND servis = 'gemini'",
                          (belge_id,)).fetchone()
    assert satir["hata_turu"] == "cikti"


@ocr_gerekli
def test_uydurma_deger_belgeyi_bekliyor_durumunda_birakir(client, monkeypatch):
    cikti = _fis_ciktisi()
    cikti["alanlar"]["toplam_tutar"] = {"deger": "999.99", "guven": 0.99}  # fişte yok
    _servis(monkeypatch, SahteCevap(200, _gemini_govdesi(cikti)))
    _, cevap = _isle(client, "ai3")
    sonuc = cevap.get_json()
    toplam = next(a for a in sonuc["alanlar"] if a["alan_adi"] == "toplam_tutar")
    assert toplam["dusuk_guven"] is True
    assert "uydurmuş" in toplam["kaynak_notu"]
    assert sonuc["durum"] == "bekliyor"  # kullanıcı kontrol etmeli


@ocr_gerekli
def test_anahtar_yoksa_kural_tabanli_calisir(client, monkeypatch):
    monkeypatch.setenv("AI_API_ANAHTARI", "")
    _, cevap = _isle(client, "ai4")
    sonuc = cevap.get_json()
    assert cevap.status_code == 201 and sonuc["yontem"] == "kural"
    assert "AI_API_ANAHTARI" in sonuc["ai_notu"]


def test_gecersiz_yontem_400(client):
    _, cevap = _isle(client, "ai5", yontem="sihir")
    assert cevap.status_code == 400
