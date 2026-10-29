"""
belge_repo.py - belgeler tablosu için CRUD fonksiyonları.

Hafta 6'da yükleme ve ön işleme için yeni fonksiyonlar eklendi:
    yukleme_kaydet, hash_ile_bul, sahibine_ait_getir
"""

import json

# Dışarıya (API'ye) verilecek kolonlar. Dosya YOLLARI bilerek yok:
# sunucudaki klasör yapısı kullanıcıya gösterilmez.
LISTE_KOLONLARI = """
    id, dosya_adi, dosya_turu, boyut_kb, durum, yuklenme_tarihi,
    genislik, yukseklik, kalite_puani, kalite_uyarilari,
    (islenmis_yol IS NOT NULL) AS on_islenmis
"""


def ekle(conn, kullanici_id, dosya_adi, dosya_yolu, dosya_turu, boyut_kb):
    """
    Yeni belge kaydı ekler (durum otomatik 'yuklendi' olur -> DEFAULT).
    kullanici_id var olmayan bir kullanıcıysa YABANCI ANAHTAR kısıtı hata verir.
    """
    return conn.execute(
        """
        INSERT INTO belgeler (kullanici_id, dosya_adi, dosya_yolu, dosya_turu, boyut_kb)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (kullanici_id, dosya_adi, dosya_yolu, dosya_turu, boyut_kb),
    ).fetchone()


def getir(conn, belge_id):
    """id ile tek belge döndürür; yoksa None."""
    return conn.execute("SELECT * FROM belgeler WHERE id = %s", (belge_id,)).fetchone()


def kullaniciya_gore_listele(conn, kullanici_id, limit=20):
    """
    Bir kullanıcının belgelerini en yeniden eskiye listeler.
    Bu sorgu idx_belgeler_kullanici_tarih indeksini kullanır
    (WHERE kullanici_id + ORDER BY yuklenme_tarihi DESC).
    """
    return conn.execute(
        """
        SELECT """ + LISTE_KOLONLARI + """
        FROM belgeler
        WHERE kullanici_id = %s
        ORDER BY yuklenme_tarihi DESC
        LIMIT %s
        """,
        (kullanici_id, limit),
    ).fetchall()


def durum_guncelle(conn, belge_id, yeni_durum):
    """
    Belgenin durumunu değiştirir ('yuklendi' -> 'islendi' / 'hatali').
    Listede olmayan bir durum yazılırsa CHECK kısıtı hata verir.
    """
    return conn.execute(
        "UPDATE belgeler SET durum = %s WHERE id = %s RETURNING *",
        (yeni_durum, belge_id),
    ).fetchone()


def sil(conn, belge_id):
    """Belgeyi siler (çıkarım kayıtları CASCADE ile silinir). True/False döndürür."""
    return conn.execute("DELETE FROM belgeler WHERE id = %s", (belge_id,)).rowcount == 1


# ======================================================== Hafta 6: yükleme
def yukleme_kaydet(conn, kullanici_id, bilgi):
    """
    Yüklenen ve ön işlenen belgeyi kaydeder.

    Parametreler:
        kullanici_id -> belgenin SAHİBİ (token'dan gelir, kullanıcıdan alınmaz)
        bilgi        -> sözlük: dosya_adi, dosya_yolu, dosya_turu, boyut_kb, durum,
                        dosya_hash, islenmis_yol, kucuk_yol, genislik, yukseklik,
                        kalite_puani, kalite_uyarilari (liste)
    %(ad)s -> sözlükteki "ad" anahtarının değeri yerine konur (adlandırılmış parametre)
    ::jsonb -> metni JSONB tipine çevirir
    """
    degerler = {**bilgi, "kullanici_id": kullanici_id,
                "kalite_uyarilari": json.dumps(bilgi["kalite_uyarilari"], ensure_ascii=False)}
    return conn.execute(
        """
        INSERT INTO belgeler (kullanici_id, dosya_adi, dosya_yolu, dosya_turu, boyut_kb, durum,
                              dosya_hash, islenmis_yol, kucuk_yol, genislik, yukseklik,
                              kalite_puani, kalite_uyarilari)
        VALUES (%(kullanici_id)s, %(dosya_adi)s, %(dosya_yolu)s, %(dosya_turu)s, %(boyut_kb)s,
                %(durum)s, %(dosya_hash)s, %(islenmis_yol)s, %(kucuk_yol)s, %(genislik)s,
                %(yukseklik)s, %(kalite_puani)s, %(kalite_uyarilari)s::jsonb)
        RETURNING """ + LISTE_KOLONLARI,
        degerler,
    ).fetchone()


def hash_ile_bul(conn, kullanici_id, dosya_hash):
    """
    Kullanıcı bu dosyayı daha önce yüklemiş mi? (aynı SHA-256 parmak izi)
    uq_belge_kullanici_hash kısıtının oluşturduğu indeks sayesinde hızlıdır.
    """
    return conn.execute(
        "SELECT id, dosya_adi FROM belgeler WHERE kullanici_id = %s AND dosya_hash = %s",
        (kullanici_id, dosya_hash),
    ).fetchone()


def sahibine_ait_getir(conn, belge_id, kullanici_id):
    """
    SAHİPLİK KONTROLÜ: Belgeyi sadece sahibi görebilir.
    WHERE'de hem belge id'si hem kullanıcı id'si aranır. Başkasının belgesi
    istenirse sonuç None olur; API bunu "bulunamadı" (404) olarak döndürür.
    Dosya yolları da döner (sadece sunucu içinde kullanılır).
    """
    return conn.execute(
        "SELECT " + LISTE_KOLONLARI + """, dosya_yolu, islenmis_yol, kucuk_yol
        FROM belgeler WHERE id = %s AND kullanici_id = %s""",
        (belge_id, kullanici_id),
    ).fetchone()
