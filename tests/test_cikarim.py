"""
test_cikarim.py - Şema tanımı ve belge işleme (OCR -> eşleme -> doğrulama -> kayıt) API testleri.

Gerçek PostgreSQL gerekir (ulaşılamazsa ATLANIR). Belge işleme testleri ayrıca
Tesseract OCR gerektirir; kurulu değilse sadece o testler ATLANIR.
"""

import io

import pytest

psycopg = pytest.importorskip("psycopg")

from app import create_app  # noqa: E402
from app.data.db import baglanti  # noqa: E402
from app.services.ocr import tesseract  # noqa: E402
from tests.ornek_belgeler import BELGELER, belge_gorseli  # noqa: E402
from tests.ornek_gorsel import bayt  # noqa: E402

PAROLA = "Deneme123"
ocr_gerekli = pytest.mark.skipif(not tesseract.kurulu_mu(), reason="Tesseract OCR kurulu değil")


@pytest.fixture
def client(tmp_path):
    try:
        with baglanti() as c:
            c.execute("SELECT anahtar_kelimeler FROM sema_alanlari LIMIT 1")  # 005 uygulanmış mı?
            if not c.execute("SELECT 1 FROM semalar WHERE ad = 'fis' AND sistem_semasi_mi").fetchone():
                pytest.skip("Sistem şemaları yok (python manage.py seed)")
    except Exception as hata:  # noqa: BLE001
        pytest.skip(f"Veritabanı hazır değil (python manage.py migrate): {hata}")

    uygulama = create_app("testing")
    uygulama.config["UPLOAD_FOLDER"] = str(tmp_path)
    yield uygulama.test_client()

    with baglanti() as c:
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _hesap(client, ad="a"):
    email = f"test_{ad}@ornek.test"
    client.post("/api/auth/kayit", json={"ad_soyad": "Test Kisi", "email": email, "parola": PAROLA})
    token = client.post("/api/auth/giris", json={"email": email, "parola": PAROLA}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _sema_id(client, b, ad):
    semalar = client.get("/api/semalar", headers=b).get_json()["semalar"]
    return next(s["id"] for s in semalar if s["ad"] == ad)


def _yukle(client, b, belge_adi):
    veri = bayt(belge_gorseli(BELGELER[belge_adi]))
    cevap = client.post("/api/belgeler", headers=b, content_type="multipart/form-data",
                        data={"dosya": (io.BytesIO(veri), f"{belge_adi}.jpg")})
    assert cevap.status_code == 201, cevap.get_json()
    return cevap.get_json()["belge"]["id"]


ORNEK_SEMA = {
    "ad": "test_makbuz", "aciklama": "Deneme",
    "alanlar": [
        {"alan_adi": "makbuz_no", "veri_tipi": "metin", "zorunlu_mu": True, "anahtar_kelimeler": "MAKBUZ NO"},
        {"alan_adi": "tutar", "veri_tipi": "para", "zorunlu_mu": True, "anahtar_kelimeler": "TUTAR"},
    ],
}


# ================================================================== ŞEMALAR
def test_sema_listesi_sistem_ve_kendi_semalarim(client):
    b = _hesap(client)
    adlar = [s["ad"] for s in client.get("/api/semalar", headers=b).get_json()["semalar"]]
    assert {"fis", "fatura", "kartvizit"} <= set(adlar)
    assert "gider_pusulasi" not in adlar  # muhasebecinin şeması bana görünmez


def test_sema_olustur_ve_sil(client):
    b = _hesap(client)
    cevap = client.post("/api/semalar", headers=b, json=ORNEK_SEMA)
    assert cevap.status_code == 201
    sema = cevap.get_json()["sema"]
    assert [a["alan_adi"] for a in sema["alanlar"]] == ["makbuz_no", "tutar"]
    assert client.post("/api/semalar", headers=b, json=ORNEK_SEMA).status_code == 409  # aynı ad
    assert client.delete(f"/api/semalar/{sema['id']}", headers=b).status_code == 200


def test_gecersiz_sema_tum_hatalari_doner(client):
    cevap = client.post("/api/semalar", headers=_hesap(client), json={
        "ad": "Kötü Ad", "alanlar": [
            {"alan_adi": "tutar", "veri_tipi": "para"},
            {"alan_adi": "tutar", "veri_tipi": "renk", "dogrulama_kurali": "[abc"},
        ]})
    assert cevap.status_code == 400
    assert len(cevap.get_json()["ayrintilar"]) == 4  # ad + tekrar + tip + regex


def test_sistem_semasi_silinemez(client):
    b = _hesap(client)
    assert client.delete(f"/api/semalar/{_sema_id(client, b, 'fis')}", headers=b).status_code == 404


# ============================================================ BELGE İŞLEME
@ocr_gerekli
def test_dogru_fis_islenir_ve_dogrulanir(client):
    b = _hesap(client)
    belge_id = _yukle(client, b, "fis_dogru")
    cevap = client.post(f"/api/belgeler/{belge_id}/isle", headers=b, json={"sema_id": _sema_id(client, b, "fis")})
    assert cevap.status_code == 201, cevap.get_json()
    sonuc = cevap.get_json()
    degerler = {a["alan_adi"]: a["deger"] for a in sonuc["alanlar"]}
    assert degerler["vergi_no"] == "1234567808"
    assert degerler["toplam_tutar"] == "247.50"
    assert degerler["kdv_tutari"] == "41.25"
    assert sonuc["durum"] == "dogrulandi"
    # Belge durumu 'islendi' oldu ve sonuç sonradan da okunabiliyor
    belge = client.get(f"/api/belgeler/{belge_id}", headers=b).get_json()["belge"]
    assert belge["durum"] == "islendi"
    assert client.get(f"/api/belgeler/{belge_id}/cikarim", headers=b).get_json()["cikarim_id"] == sonuc["cikarim_id"]


@ocr_gerekli
def test_kdv_tutarsiz_fis_bekliyor_durumunda(client):
    b = _hesap(client)
    belge_id = _yukle(client, b, "fis_kdv_hatali")
    sonuc = client.post(f"/api/belgeler/{belge_id}/isle", headers=b,
                        json={"sema_id": _sema_id(client, b, "fis")}).get_json()
    assert sonuc["durum"] == "bekliyor"
    assert any(not k["gecerli"] for k in sonuc["kural_sonuclari"])


@ocr_gerekli
def test_hatali_vergi_no_isaretlenir(client):
    b = _hesap(client)
    belge_id = _yukle(client, b, "fis_vkn_hatali")
    sonuc = client.post(f"/api/belgeler/{belge_id}/isle", headers=b,
                        json={"sema_id": _sema_id(client, b, "fis")}).get_json()
    vergi = next(a for a in sonuc["alanlar"] if a["alan_adi"] == "vergi_no")
    assert vergi["gecerli_mi"] is False and "kontrol hanesi" in vergi["hata_mesaji"]


def test_baskasinin_belgesi_ve_semasi_kullanilamaz(client):
    ali, ayse = _hesap(client, "ali"), _hesap(client, "ayse")
    belge_id = _yukle(client, ali, "fis_dogru")
    sema = client.post("/api/semalar", headers=ali, json=ORNEK_SEMA).get_json()["sema"]
    # Ayşe, Ali'nin belgesini işleyemez
    assert client.post(f"/api/belgeler/{belge_id}/isle", headers=ayse,
                       json={"sema_id": _sema_id(client, ayse, "fis")}).status_code == 404
    # Ayşe kendi belgesini Ali'nin şemasıyla işleyemez
    kendi = _yukle(client, ayse, "fatura")
    assert client.post(f"/api/belgeler/{kendi}/isle", headers=ayse,
                       json={"sema_id": sema["id"]}).status_code == 404


def test_pdf_islenemez(client):
    b = _hesap(client)
    cevap = client.post("/api/belgeler", headers=b, content_type="multipart/form-data",
                        data={"dosya": (io.BytesIO(b"%PDF-1.4 ornek"), "f.pdf")})
    belge_id = cevap.get_json()["belge"]["id"]
    assert client.post(f"/api/belgeler/{belge_id}/isle", headers=b,
                       json={"sema_id": _sema_id(client, b, "fis")}).status_code == 400


@ocr_gerekli
def test_kullanimdaki_sema_silinemez(client):
    b = _hesap(client)
    sema = client.post("/api/semalar", headers=b, json=ORNEK_SEMA).get_json()["sema"]
    belge_id = _yukle(client, b, "fis_dogru")
    client.post(f"/api/belgeler/{belge_id}/isle", headers=b, json={"sema_id": sema["id"]})
    assert client.delete(f"/api/semalar/{sema['id']}", headers=b).status_code == 409
