"""
test_belgeler.py - Belge yükleme API'si testleri (iş kuralları, sahiplik, kredi).

Gerçek PostgreSQL gerekir; ulaşılamazsa ATLANIR.
Dosyalar geçici bir klasöre yazılır (tmp_path), gerçek uploads/ kirlenmez.
"""

import io

import pytest

psycopg = pytest.importorskip("psycopg")

from app import create_app  # noqa: E402
from app.data.db import baglanti  # noqa: E402
from tests.ornek_gorsel import bayt, fis  # noqa: E402

PAROLA = "Deneme123"


@pytest.fixture
def app(tmp_path):
    try:
        with baglanti() as c:
            c.execute("SELECT kalite_puani FROM belgeler LIMIT 1")  # 004 uygulanmış mı?
    except Exception as hata:
        pytest.skip(f"Veritabanı hazır değil (python manage.py migrate): {hata}")

    uygulama = create_app("testing")
    uygulama.config["UPLOAD_FOLDER"] = str(tmp_path)  # pytest'in verdiği geçici klasör
    yield uygulama

    with baglanti() as c:
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _hesap(client, ad="a"):
    """Test hesabı açar, giriş yapar, Authorization başlığını döndürür."""
    email = f"test_{ad}@ornek.test"
    client.post("/api/auth/kayit", json={"ad_soyad": "Test Kisi", "email": email, "parola": PAROLA})
    token = client.post("/api/auth/giris", json={"email": email, "parola": PAROLA}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _yukle(client, baslik, veri, ad="fis.jpg"):
    """multipart/form-data ile dosya gönderir: (dosya_nesnesi, dosya_adi)"""
    return client.post("/api/belgeler", headers=baslik,
                       data={"dosya": (io.BytesIO(veri), ad)}, content_type="multipart/form-data")


# ------------------------------------------------------------------ yükleme
def test_yukleme_on_isler_ve_kredi_duser(app, tmp_path):
    client = app.test_client()
    b = _hesap(client)
    cevap = _yukle(client, b, bayt(fis()))
    assert cevap.status_code == 201
    veri = cevap.get_json()
    assert veri["belge"]["durum"] == "on_islendi"
    assert veri["belge"]["kalite_puani"] == 100
    assert veri["kalan_kredi"] == 19          # 20 - 1
    assert "dosya_yolu" not in veri["belge"]  # sunucu yolu dışarı sızmamalı
    # orijinal + işlenmiş + küçük = 3 dosya diske yazıldı
    assert len(list(tmp_path.rglob("*.*"))) == 3


def test_tokensiz_yukleme_yapilamaz(app):
    assert _yukle(app.test_client(), {}, bayt(fis())).status_code == 401


def test_izin_verilmeyen_tur_reddedilir(app):
    client = app.test_client()
    cevap = _yukle(client, _hesap(client), b"MZ...", ad="virus.exe")
    assert cevap.status_code == 400


def test_dusuk_kaliteli_gorsel_reddedilir_kredi_dusmez(app):
    client = app.test_client()
    b = _hesap(client)
    cevap = _yukle(client, b, bayt(fis(bozulma="cok_bulanik")))
    assert cevap.status_code == 400
    assert client.get("/api/belgeler", headers=b).get_json()["kalan_kredi"] == 20


def test_ayni_dosya_iki_kez_yuklenemez(app):
    client = app.test_client()
    b = _hesap(client)
    veri = bayt(fis())
    assert _yukle(client, b, veri).status_code == 201
    assert _yukle(client, b, veri, ad="baska_ad.jpg").status_code == 409


def test_kredi_bitince_yukleme_yapilamaz(app):
    client = app.test_client()
    b = _hesap(client)
    with baglanti() as c:
        c.execute("""UPDATE abonelikler SET kalan_kredi = 0 WHERE kullanici_id =
                     (SELECT id FROM kullanicilar WHERE email = 'test_a@ornek.test')""")
    assert _yukle(client, b, bayt(fis())).status_code == 402


def test_pdf_kabul_edilir_sahte_pdf_reddedilir(app):
    client = app.test_client()
    b = _hesap(client)
    assert _yukle(client, b, b"%PDF-1.4 ornek", ad="fatura.pdf").status_code == 201
    assert _yukle(client, b, b"pdf degil", ad="sahte.pdf").status_code == 400


# -------------------------------------------------------------- sahiplik
def test_baskasinin_belgesi_gorulemez_silinemez(app):
    client = app.test_client()
    ali, ayse = _hesap(client, "ali"), _hesap(client, "ayse")
    belge_id = _yukle(client, ali, bayt(fis())).get_json()["belge"]["id"]

    assert client.get(f"/api/belgeler/{belge_id}", headers=ayse).status_code == 404
    assert client.get(f"/api/belgeler/{belge_id}/gorsel", headers=ayse).status_code == 404
    assert client.delete(f"/api/belgeler/{belge_id}", headers=ayse).status_code == 404
    assert client.get("/api/belgeler", headers=ayse).get_json()["belgeler"] == []
    # sahibi görebilir
    assert client.get(f"/api/belgeler/{belge_id}", headers=ali).status_code == 200


def test_gorsel_indirilir_ve_silinince_dosyalar_gider(app, tmp_path):
    client = app.test_client()
    b = _hesap(client)
    belge_id = _yukle(client, b, bayt(fis())).get_json()["belge"]["id"]

    cevap = client.get(f"/api/belgeler/{belge_id}/gorsel?tur=islenmis", headers=b)
    assert cevap.status_code == 200 and cevap.mimetype == "image/png"
    assert cevap.data[:4] == b"\x89PNG"  # PNG dosyaları bu baytlarla başlar
    cevap.close()

    assert client.delete(f"/api/belgeler/{belge_id}", headers=b).status_code == 200
    assert list(tmp_path.rglob("*.*")) == []  # diskte dosya kalmadı


def test_10mb_ustu_dosya_reddedilir(app):
    client = app.test_client()
    cevap = _yukle(client, _hesap(client), b"0" * (11 * 1024 * 1024))
    assert cevap.status_code == 413
    assert "10 MB" in cevap.get_json()["hata"]
