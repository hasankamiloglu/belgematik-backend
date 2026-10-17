"""
manage.py - Veritabanı yönetim komutları.

Kullanım (sanal ortam aktifken, backend klasöründe):
    python manage.py migrate   -> Tabloları ve indeksleri oluşturur (migration'ları uygular)
    python manage.py seed      -> Sentetik örnek veriyi yükler (önce tabloları boşaltır!)
    python manage.py demo      -> CRUD işlemlerini adım adım çalıştırıp ekrana yazar
    python manage.py sorgular  -> db/sorgular/ornek_sorgular.sql içindeki sorguları çalıştırır
    python manage.py yonetici EMAIL -> Bu e-postadaki hesabı YÖNETİCİ yapar (Hafta 5)

Yönetici yetkisi web sitesinden VERİLEMEZ; sadece sunucuya erişimi olan kişi
bu komutla verebilir. Böylece kimse kendini yönetici yapamaz.
"""

import sys
from pathlib import Path

from app.data import migrate as migrasyon
from app.data.db import baglanti

KOK = Path(__file__).resolve().parent


def _okunakli(satir):
    """
    Sorgu sonucundaki satırı ekrana okunaklı yazmak için sadeleştirir.
    Veritabanından gelen tarih (datetime) ve ondalık sayı (Decimal) değerleri
    Python'da  datetime.datetime(2026, 10, 16, ...)  gibi uzun görünür;
    str() ile  2026-10-16 08:34:25  gibi kısa metne çeviriyoruz.
    """
    sade = {}
    for anahtar, deger in dict(satir).items():
        if deger is None or isinstance(deger, (bool, int, str)):
            sade[anahtar] = deger
        elif hasattr(deger, "strftime"):  # tarih / saat
            sade[anahtar] = deger.strftime("%Y-%m-%d %H:%M:%S")
        else:  # Decimal gibi diğer tipler
            sade[anahtar] = str(deger)
    return sade


def komut_migrate():
    with baglanti() as conn:
        yeni = migrasyon.migrate(conn)
        if yeni:
            for ad in yeni:
                print(f"  ✔ uygulandı: {ad}")
        else:
            print("  Uygulanacak yeni migration yok, şema güncel.")
        print("Toplam uygulanmış migration:", len(migrasyon.uygulananlar(conn)))


def komut_seed():
    sql = (KOK / "db" / "seed" / "ornek_veri.sql").read_text(encoding="utf-8")
    with baglanti() as conn:
        with conn.transaction():  # ya hepsi yüklenir ya hiçbiri
            conn.execute(sql)
        sayilar = conn.execute(
            """
            SELECT (SELECT count(*) FROM kullanicilar)      AS kullanicilar,
                   (SELECT count(*) FROM abonelikler)       AS abonelikler,
                   (SELECT count(*) FROM semalar)           AS semalar,
                   (SELECT count(*) FROM sema_alanlari)     AS sema_alanlari,
                   (SELECT count(*) FROM belgeler)          AS belgeler,
                   (SELECT count(*) FROM cikarim_kayitlari) AS cikarim_kayitlari,
                   (SELECT count(*) FROM cikarim_degerleri) AS cikarim_degerleri
            """
        ).fetchone()
    print("Örnek veri yüklendi:")
    for tablo, sayi in sayilar.items():
        print(f"  {tablo:<20} {sayi} satır")


def komut_sorgular():
    metin = (KOK / "db" / "sorgular" / "ornek_sorgular.sql").read_text(encoding="utf-8")
    # Dosyayı ";" işaretlerinden bölüp her sorguyu ayrı çalıştırıyoruz
    sorgular = [s.strip() for s in metin.split(";") if "SELECT" in s.upper()]
    with baglanti() as conn:
        for sorgu in sorgular:
            satirlar = [l for l in sorgu.splitlines() if not l.strip().startswith("--")]
            # Başlık: "-- 1) ..." biçimindeki açıklama satırı
            baslik = next(l for l in sorgu.splitlines() if l.strip()[3:4].isdigit())
            print("\n" + baslik.strip("- ").strip())
            for satir in conn.execute("\n".join(satirlar)).fetchall():
                print("   ", _okunakli(satir))


def komut_demo():
    # Demo, gerçek CRUD fonksiyonlarını kullanır (app/data/repositories/)
    from app.data.repositories import belge_repo, cikarim_repo, kullanici_repo

    with baglanti() as conn:
        print("\n[CREATE] Yeni kullanıcı + ücretsiz abonelik (tek transaction):")
        k = kullanici_repo.abonelikli_ekle(conn, "Demo Kisi", "demo@ornek.test", "sahte-hash", "kobi")
        print("   ", _okunakli(k))

        print("\n[READ] E-posta ile kullanıcı getir:")
        print("   ", _okunakli(kullanici_repo.email_ile_getir(conn, "demo@ornek.test")))

        print("\n[UPDATE] Rolü 'muhasebeci' yap:")
        print("   ", _okunakli(kullanici_repo.guncelle(conn, k["id"], rol="muhasebeci")))

        print("\n[CREATE] Kullanıcıya belge ekle:")
        b = belge_repo.ekle(conn, k["id"], "demo_fis.jpg", "uploads/demo_fis.jpg", "jpg", 300)
        print("   ", _okunakli(b))

        print("\n[READ] Kullanıcının belgeleri (idx_belgeler_kullanici_tarih indeksi):")
        for satir in belge_repo.kullaniciya_gore_listele(conn, k["id"]):
            print("   ", _okunakli(satir))

        print("\n[CREATE] Çıkarım kaydı + değerleri (tek transaction):")
        c = cikarim_repo.kaydet(
            conn, b["id"], "fis", "tesseract", "DEMO MARKET TOPLAM 100,00", 0.85,
            {"firma_adi": "Demo Market (Örnek)", "toplam_tutar": "100.00", "kdv_tutari": "9.09"},
        )
        for satir in cikarim_repo.degerleri_getir(conn, c["id"]):
            print("   ", _okunakli(satir))

        print("\n[UPDATE] Kullanıcı bir değeri düzeltti:")
        print("   ", _okunakli(cikarim_repo.deger_duzelt(conn, c["id"], "kdv_tutari", "9.10")))

        print("\n[DELETE] Demo kullanıcıyı sil (belgesi ve çıkarımları CASCADE ile silinir):")
        print("    silindi mi?", kullanici_repo.sil(conn, k["id"]))
        print("    belge hâlâ var mı?", belge_repo.getir(conn, b["id"]) is not None)


def komut_yonetici(email):
    from app.services.auth.kimlik_servisi import yetki_ver

    sonuc = yetki_ver(email, "yonetici")
    if sonuc is None:
        print(f"  ✘ '{email}' adresiyle kayıtlı kullanıcı bulunamadı.")
    else:
        print(f"  ✔ {sonuc['email']} artık yönetici. (Eski oturumları kapatıldı, tekrar giriş yapmalı.)")


KOMUTLAR = {
    "migrate": komut_migrate,
    "seed": komut_seed,
    "demo": komut_demo,
    "sorgular": komut_sorgular,
    "yonetici": komut_yonetici,  # e-posta parametresi alır
}

if __name__ == "__main__":
    # sys.argv -> komut satırında yazılanlar. "python manage.py seed" -> ["manage.py", "seed"]
    # "python manage.py yonetici ali@ornek.test" -> ["manage.py", "yonetici", "ali@ornek.test"]
    if len(sys.argv) < 2 or sys.argv[1] not in KOMUTLAR:
        print(__doc__)
        sys.exit(1)
    komut, parametreler = sys.argv[1], sys.argv[2:]
    if komut == "yonetici" and len(parametreler) != 1:
        print("Kullanım: python manage.py yonetici EMAIL")
        sys.exit(1)
    KOMUTLAR[komut](*parametreler)
