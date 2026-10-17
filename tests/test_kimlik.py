"""
test_kimlik.py - Kayıt, giriş, oturum ve rol tabanlı erişim testleri (API üzerinden).

Gerçek PostgreSQL gerekir; ulaşılamazsa testler ATLANIR.
Test hesapları "test_" ile başlar ve her testten sonra silinir.
"""

import pytest

psycopg = pytest.importorskip("psycopg")

from app import create_app  # noqa: E402
from app.data.db import baglanti  # noqa: E402
from app.services.auth import kimlik_servisi  # noqa: E402

PAROLA = "Deneme123"


@pytest.fixture
def client():
    """Veritabanı hazır değilse atla; test bitince test kayıtlarını temizle."""
    try:
        with baglanti() as c:
            c.execute("SELECT yetki FROM kullanicilar LIMIT 1")  # 003 migration'ı uygulanmış mı?
    except Exception as hata:
        pytest.skip(f"Veritabanı hazır değil (python manage.py migrate): {hata}")

    yield create_app("testing").test_client()

    with baglanti() as c:
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _kayit(client, email="test_a@ornek.test", parola=PAROLA, **ek):
    return client.post("/api/auth/kayit", json={
        "ad_soyad": "Test Kisi", "email": email, "parola": parola, **ek
    })


def _giris(client, email="test_a@ornek.test", parola=PAROLA):
    return client.post("/api/auth/giris", json={"email": email, "parola": parola})


def _baslik(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------- kayıt
def test_kayit_basarili_ve_parola_hashli(client):
    cevap = _kayit(client)
    assert cevap.status_code == 201
    veri = cevap.get_json()["kullanici"]
    assert veri["yetki"] == "kullanici"
    assert "sifre_hash" not in veri  # hash dışarı sızmamalı

    with baglanti() as c:
        satir = c.execute(
            "SELECT sifre_hash FROM kullanicilar WHERE email = 'test_a@ornek.test'"
        ).fetchone()
    assert satir["sifre_hash"] != PAROLA            # düz metin DEĞİL
    assert satir["sifre_hash"].startswith("pbkdf2_sha256$")


def test_ayni_email_ikinci_kez_kayit_olamaz(client):
    _kayit(client)
    assert _kayit(client, email="TEST_A@ornek.test ").status_code == 409  # büyük harf/boşluk fark etmez


def test_zayif_parola_reddedilir(client):
    cevap = _kayit(client, parola="123")
    assert cevap.status_code == 400
    assert cevap.get_json()["ayrintilar"]


def test_kayitta_kendini_yonetici_yapamaz(client):
    """İstekte yetki='yonetici' gönderilse bile hesap 'kullanici' olmalı."""
    cevap = _kayit(client, yetki="yonetici")
    assert cevap.get_json()["kullanici"]["yetki"] == "kullanici"


# ------------------------------------------------------------------- giriş
def test_giris_basarili_token_verir(client):
    _kayit(client)
    cevap = _giris(client)
    assert cevap.status_code == 200
    assert cevap.get_json()["token"].count(".") == 2  # JWT: 3 parça


def test_yanlis_parola_ve_olmayan_email_ayni_mesaj(client):
    """Saldırgan hangi e-postanın kayıtlı olduğunu mesajdan anlayamamalı."""
    _kayit(client)
    yanlis_parola = _giris(client, parola="Yanlis999")
    olmayan_email = _giris(client, email="test_yok@ornek.test")
    assert yanlis_parola.status_code == olmayan_email.status_code == 401
    assert yanlis_parola.get_json() == olmayan_email.get_json()


def test_bes_hatali_denemede_hesap_kilitlenir(client):
    _kayit(client)
    for _ in range(4):
        assert _giris(client, parola="Yanlis999").status_code == 401
    assert _giris(client, parola="Yanlis999").status_code == 429  # 5. deneme -> kilit
    # Kilitliyken DOĞRU parola da kabul edilmez
    assert _giris(client).status_code == 429


def test_giris_denemeleri_kaydediliyor(client):
    _kayit(client)
    _giris(client, parola="Yanlis999")
    _giris(client)
    with baglanti() as c:
        satirlar = c.execute(
            "SELECT basarili FROM giris_denemeleri WHERE email = 'test_a@ornek.test' ORDER BY id"
        ).fetchall()
    assert [s["basarili"] for s in satirlar] == [False, True]


# ------------------------------------------------------- oturum / yetki
def test_tokensiz_korumali_uca_erisilemez(client):
    assert client.get("/api/auth/ben").status_code == 401
    assert client.get("/api/yonetici/kullanicilar").status_code == 401


def test_bozuk_token_reddedilir(client):
    assert client.get("/api/auth/ben", headers=_baslik("abc.def.ghi")).status_code == 401


def test_token_ile_ben(client):
    _kayit(client)
    token = _giris(client).get_json()["token"]
    cevap = client.get("/api/auth/ben", headers=_baslik(token))
    assert cevap.status_code == 200
    assert cevap.get_json()["kullanici"]["email"] == "test_a@ornek.test"


def test_normal_kullanici_yonetici_sayfasina_giremez(client):
    _kayit(client)
    token = _giris(client).get_json()["token"]
    assert client.get("/api/yonetici/kullanicilar", headers=_baslik(token)).status_code == 403


def test_yonetici_sayfaya_girebilir(client):
    _kayit(client, email="test_yon@ornek.test")
    kimlik_servisi.yetki_ver("test_yon@ornek.test", "yonetici")
    token = _giris(client, email="test_yon@ornek.test").get_json()["token"]
    cevap = client.get("/api/yonetici/kullanicilar", headers=_baslik(token))
    assert cevap.status_code == 200
    assert "kullanicilar" in cevap.get_json()


def test_cikistan_sonra_eski_token_gecersiz(client):
    _kayit(client)
    token = _giris(client).get_json()["token"]
    assert client.post("/api/auth/cikis", headers=_baslik(token)).status_code == 200
    assert client.get("/api/auth/ben", headers=_baslik(token)).status_code == 401
