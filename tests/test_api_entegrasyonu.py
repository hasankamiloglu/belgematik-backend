"""
test_api_entegrasyonu.py - Harici OCR API'nin belge işleme akışına bağlanması (Hafta 9).

Akış: yükle -> işle (harici API SAHTE cevap verir) -> sonuç kaydedilir -> çağrı günlüğe yazılır
      -> yönetici panelinde görünür.
Gerçek PostgreSQL gerekir (ulaşılamazsa ATLANIR). İnternete ÇIKILMAZ.
"""

import io

import pytest

psycopg = pytest.importorskip("psycopg")

from app import create_app  # noqa: E402
from app.data.db import baglanti  # noqa: E402
from app.services.auth import kimlik_servisi  # noqa: E402
from app.services.ocr import harici_api, tesseract  # noqa: E402
from tests.ornek_belgeler import BELGELER, belge_gorseli  # noqa: E402
from tests.ornek_gorsel import bayt  # noqa: E402
from tests.test_harici_api import BASARILI_GOVDE, SahteCevap, SahteServis  # noqa: E402

PAROLA = "Deneme123"

# Sahte API'nin döndürdüğü metin: doğru fişin satırları (eşleyici bunlardan alanları bulur)
FIS_GOVDESI = {"ParsedResults": [{"ParsedText": "\r\n".join(BELGELER["fis_dogru"])}],
               "IsErroredOnProcessing": False}


@pytest.fixture
def client(tmp_path, monkeypatch):
    try:
        with baglanti() as c:
            c.execute("SELECT 1 FROM api_cagrilari LIMIT 1")  # migration 006 uygulanmış mı?
            if not c.execute("SELECT 1 FROM semalar WHERE ad = 'fis' AND sistem_semasi_mi").fetchone():
                pytest.skip("Sistem şemaları yok (python manage.py seed)")
    except Exception as hata:  # noqa: BLE001
        pytest.skip(f"Veritabanı hazır değil (python manage.py migrate): {hata}")

    monkeypatch.setenv("OCR_API_ANAHTARI", "TEST_ANAHTARI_12345678")
    monkeypatch.setenv("OCR_API_DAKIKA_SINIRI", "100")
    monkeypatch.setattr(harici_api, "_sinirlayici", None)

    uygulama = create_app("testing")
    uygulama.config["UPLOAD_FOLDER"] = str(tmp_path)
    yield uygulama.test_client()

    with baglanti() as c:
        # Testin sahte API çağrıları gerçek günlükte (yönetici paneli) kalmasın
        c.execute("""DELETE FROM api_cagrilari WHERE kullanici_id IN
                     (SELECT id FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test')""")
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _hesap(client, ad, yonetici=False):
    email = f"test_{ad}@ornek.test"
    client.post("/api/auth/kayit", json={"ad_soyad": "Test Kisi", "email": email, "parola": PAROLA})
    if yonetici:
        kimlik_servisi.yetki_ver(email, "yonetici")
    token = client.post("/api/auth/giris", json={"email": email, "parola": PAROLA}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _yukle_ve_isle(client, b):
    veri = bayt(belge_gorseli(BELGELER["fis_dogru"]))
    belge = client.post("/api/belgeler", headers=b, content_type="multipart/form-data",
                        data={"dosya": (io.BytesIO(veri), "fis.jpg")}).get_json()["belge"]
    semalar = client.get("/api/semalar", headers=b).get_json()["semalar"]
    sema_id = next(s["id"] for s in semalar if s["ad"] == "fis")
    return belge["id"], client.post(f"/api/belgeler/{belge['id']}/isle", headers=b,
                                    json={"sema_id": sema_id})


def _gunluk(belge_id):
    with baglanti() as c:
        return c.execute("SELECT * FROM api_cagrilari WHERE belge_id = %s", (belge_id,)).fetchall()


def test_api_ile_islenen_fis_kaydedilir_ve_gunluge_yazilir(client, monkeypatch):
    monkeypatch.setenv("OCR_MOTORU", "api")
    monkeypatch.setattr(harici_api.requests, "post", SahteServis(SahteCevap(200, FIS_GOVDESI)))
    b = _hesap(client, "api1")

    belge_id, cevap = _yukle_ve_isle(client, b)
    assert cevap.status_code == 201, cevap.get_json()
    sonuc = cevap.get_json()
    assert sonuc["ocr_motoru"] == "ocr_space"
    assert sonuc["ocr_notu"] is None
    alanlar = {a["alan_adi"]: a["deger"] for a in sonuc["alanlar"]}
    assert alanlar["toplam_tutar"] is not None  # API'nin metninden alan eşlendi

    gunluk = _gunluk(belge_id)
    assert len(gunluk) == 1 and gunluk[0]["durum"] == "basarili"
    assert "TEST_ANAHTARI" not in str(dict(gunluk[0]))  # anahtar günlüğe yazılmaz


@pytest.mark.skipif(not tesseract.kurulu_mu(), reason="Tesseract OCR kurulu değil")
def test_api_hata_verirse_tesseract_ile_devam_edilir(client, monkeypatch):
    monkeypatch.setenv("OCR_MOTORU", "otomatik")
    monkeypatch.setattr(harici_api.requests, "post", SahteServis(SahteCevap(403, metin="invalid key")))
    b = _hesap(client, "api2")

    belge_id, cevap = _yukle_ve_isle(client, b)
    assert cevap.status_code == 201
    sonuc = cevap.get_json()
    assert sonuc["ocr_motoru"] == "tesseract"
    assert "Tesseract ile okundu" in sonuc["ocr_notu"]

    gunluk = _gunluk(belge_id)
    assert gunluk[0]["durum"] == "hata" and gunluk[0]["hata_turu"] == "kimlik"
    assert gunluk[0]["http_kodu"] == 403


def test_sadece_api_modunda_hata_503_doner(client, monkeypatch):
    monkeypatch.setenv("OCR_MOTORU", "api")
    import requests

    monkeypatch.setattr(harici_api.requests, "post", SahteServis(requests.Timeout()))
    monkeypatch.setattr(harici_api, "ILK_BEKLEME", 0)  # testte gerçekten bekleme
    b = _hesap(client, "api3")

    belge_id, cevap = _yukle_ve_isle(client, b)
    assert cevap.status_code == 503
    assert "zaman aşımı" in cevap.get_json()["hata"]
    assert _gunluk(belge_id)[0]["deneme_sayisi"] == 3


def test_yonetici_api_cagrilarini_gorur_normal_kullanici_goremez(client, monkeypatch):
    monkeypatch.setenv("OCR_MOTORU", "api")
    monkeypatch.setattr(harici_api.requests, "post", SahteServis(SahteCevap(200, BASARILI_GOVDE)))
    normal = _hesap(client, "api4")
    _yukle_ve_isle(client, normal)

    assert client.get("/api/yonetici/api-cagrilari", headers=normal).status_code == 403

    yonetici = _hesap(client, "api5", yonetici=True)
    veri = client.get("/api/yonetici/api-cagrilari", headers=yonetici).get_json()
    assert veri["anahtar"] == "TE****5678"           # sadece maskeli
    assert "TEST_ANAHTARI_12345678" not in str(veri)  # gerçek anahtar asla dönmez
    assert veri["son_24_saat"]["basarili"] >= 1
    assert any(c["email"] == "test_api4@ornek.test" for c in veri["cagrilar"])
