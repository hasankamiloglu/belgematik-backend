"""
test_uctan_uca.py - UÇTAN UCA ENTEGRASYON TESTİ (Hafta 8, ara sürüm v0.7.0)

Diğer testler modülleri TEK TEK dener (birim test). Bu test ise bir kullanıcının
uygulamayı baştan sona kullanmasını taklit eder ve TÜM modüllerin birlikte
çalıştığını kanıtlar:

    Hafta 5  kayıt ol ─▶ giriş yap (token) ─▶ /ben
    Hafta 6  fiş yükle ─▶ kalite + ön işleme ─▶ kredi düştü
    Hafta 7  şema seç ─▶ OCR ─▶ alan eşleme ─▶ doğrulama ─▶ kayıt
    Hafta 4  her adımın sonucu veritabanında doğru tablolarda mı?
    Hafta 5  yönetici kullanıcıyı görüyor ─▶ çıkış ─▶ eski token geçersiz

Herhangi bir modül diğerini bozarsa (ör. ön işleme görselin yolunu değiştirirse
OCR bulamaz) bu test kırılır. Buna REGRESYON testi denir: yeni kod eskiyi bozdu mu?

Gerçek PostgreSQL ve Tesseract gerekir; yoksa ATLANIR.
"""

import io

import pytest

psycopg = pytest.importorskip("psycopg")

from app import create_app  # noqa: E402
from app.data.db import baglanti  # noqa: E402
from app.services.ocr import tesseract  # noqa: E402
from tests.ornek_belgeler import BELGELER, belge_gorseli  # noqa: E402
from tests.ornek_gorsel import bayt  # noqa: E402

EMAIL = "test_senaryo@ornek.test"
PAROLA = "Senaryo2026"


@pytest.fixture
def client(tmp_path):
    if not tesseract.kurulu_mu():
        pytest.skip("Tesseract OCR kurulu değil")
    try:
        with baglanti() as c:
            if not c.execute("SELECT 1 FROM semalar WHERE ad = 'fis' AND sistem_semasi_mi").fetchone():
                pytest.skip("Sistem şemaları yok (python manage.py seed)")
    except Exception as hata:  # noqa: BLE001
        pytest.skip(f"Veritabanı hazır değil: {hata}")

    uygulama = create_app("testing")
    uygulama.config["UPLOAD_FOLDER"] = str(tmp_path)
    yield uygulama.test_client()

    with baglanti() as c:
        c.execute("DELETE FROM kullanicilar WHERE email LIKE 'test\\_%%@ornek.test'")
        c.execute("DELETE FROM giris_denemeleri WHERE email LIKE 'test\\_%%@ornek.test'")


def _yonetici_tokeni(client):
    """Örnek verideki yönetici hesabıyla giriş (seed: yonetici@ornek.test / Deneme123)."""
    cevap = client.post("/api/auth/giris", json={"email": "yonetici@ornek.test", "parola": "Deneme123"})
    if cevap.status_code != 200:
        pytest.skip("Örnek yönetici hesabı yok (python manage.py seed)")
    return cevap.get_json()["token"]


def test_kullanici_senaryosu_bastan_sona(client):
    # ---------------------------------------------------------- 1) KAYIT + GİRİŞ (Hafta 5)
    cevap = client.post("/api/auth/kayit", json={
        "ad_soyad": "Senaryo Kullanici", "email": EMAIL, "parola": PAROLA, "rol": "kobi"})
    assert cevap.status_code == 201, cevap.get_json()

    cevap = client.post("/api/auth/giris", json={"email": EMAIL, "parola": PAROLA})
    assert cevap.status_code == 200
    b = {"Authorization": f"Bearer {cevap.get_json()['token']}"}

    ben = client.get("/api/auth/ben", headers=b).get_json()["kullanici"]
    assert ben["rol"] == "kobi" and ben["kalan_kredi"] == 20  # kayıtta 20 ücretsiz kredi

    # ------------------------------------------------- 2) YÜKLEME + ÖN İŞLEME (Hafta 6)
    veri = bayt(belge_gorseli(BELGELER["fis_dogru"]))
    cevap = client.post("/api/belgeler", headers=b, content_type="multipart/form-data",
                        data={"dosya": (io.BytesIO(veri), "market_fisi.jpg")})
    assert cevap.status_code == 201, cevap.get_json()
    belge = cevap.get_json()["belge"]
    assert belge["durum"] == "on_islendi" and belge["kalite_puani"] >= 80
    assert cevap.get_json()["kalan_kredi"] == 19

    # ---------------------------------------- 3) OCR + EŞLEME + DOĞRULAMA (Hafta 7)
    semalar = client.get("/api/semalar", headers=b).get_json()["semalar"]
    fis_id = next(s["id"] for s in semalar if s["ad"] == "fis")
    cevap = client.post(f"/api/belgeler/{belge['id']}/isle", headers=b, json={"sema_id": fis_id})
    assert cevap.status_code == 201, cevap.get_json()
    sonuc = cevap.get_json()
    degerler = {a["alan_adi"]: a["deger"] for a in sonuc["alanlar"]}
    assert degerler["vergi_no"] == "1234567808"
    assert degerler["tarih"] == "2026-10-12"
    assert degerler["kdv_tutari"] == "41.25"
    assert degerler["toplam_tutar"] == "247.50"
    assert sonuc["durum"] == "dogrulandi"
    assert all(k["gecerli"] for k in sonuc["kural_sonuclari"])

    # ------------------------------------------- 4) VERİTABANI TUTARLILIĞI (Hafta 4)
    with baglanti() as c:
        satir = c.execute(
            """
            SELECT b.durum AS belge_durumu, a.kalan_kredi,
                   (SELECT count(*) FROM cikarim_kayitlari ck WHERE ck.belge_id = b.id) AS cikarim_sayisi,
                   (SELECT count(*) FROM cikarim_degerleri cd
                      JOIN cikarim_kayitlari ck ON ck.id = cd.cikarim_id
                     WHERE ck.belge_id = b.id) AS deger_sayisi
            FROM belgeler b
            JOIN abonelikler a ON a.kullanici_id = b.kullanici_id
            WHERE b.id = %s
            """,
            (belge["id"],),
        ).fetchone()
    assert satir["belge_durumu"] == "islendi"
    assert satir["kalan_kredi"] == 19          # işleme ek kredi harcamadı
    assert satir["cikarim_sayisi"] == 1
    assert satir["deger_sayisi"] == 7          # fiş şemasının 7 alanı (N-N ara tablo)

    # ------------------------------------- 5) YÖNETİCİ + ÇIKIŞ (Hafta 5)
    yonetici = {"Authorization": f"Bearer {_yonetici_tokeni(client)}"}
    liste = client.get("/api/yonetici/kullanicilar", headers=yonetici).get_json()["kullanicilar"]
    assert EMAIL in [k["email"] for k in liste]
    # normal kullanıcı yönetici sayfasına giremez
    assert client.get("/api/yonetici/kullanicilar", headers=b).status_code == 403

    assert client.post("/api/auth/cikis", headers=b).status_code == 200
    assert client.get("/api/belgeler", headers=b).status_code == 401  # eski token artık geçersiz


def test_api_surumu_ara_surumle_ayni(client):
    """/api/saglik'teki sürüm, Git etiketiyle (v0.7.0) aynı olmalı."""
    assert client.get("/api/saglik").get_json()["surum"] == "0.7.0"
