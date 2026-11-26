"""
api_repo.py - Harici API çağrı günlüğü (VERİ katmanı, Hafta 9).

Tablo: api_cagrilari (migration 006). API anahtarı bu tabloya asla yazılmaz.
"""


def kaydet(conn, kullanici_id, belge_id, servis, durum, hata_turu, http_kodu,
           deneme_sayisi, sure_ms, hata_mesaji):
    """Bir API çağrısını günlüğe ekler."""
    conn.execute(
        """
        INSERT INTO api_cagrilari (kullanici_id, belge_id, servis, durum, hata_turu,
                                   http_kodu, deneme_sayisi, sure_ms, hata_mesaji)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (kullanici_id, belge_id, servis, durum, hata_turu, http_kodu,
         deneme_sayisi, sure_ms, (hata_mesaji or None) and hata_mesaji[:300]),
    )


def son_cagrilar(conn, limit=30):
    """En yeni çağrılar (yönetici paneli). Kullanıcının e-postası JOIN ile gelir."""
    return conn.execute(
        """
        SELECT a.id, a.tarih, a.servis, a.durum, a.hata_turu, a.http_kodu,
               a.deneme_sayisi, a.sure_ms, a.hata_mesaji, a.belge_id, k.email
        FROM api_cagrilari a
        LEFT JOIN kullanicilar k ON k.id = a.kullanici_id
        ORDER BY a.id DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()


def son_24_saat_ozeti(conn):
    """Son 24 saatte kaç çağrı, kaçı başarılı, ortalama süre (hız sınırına yakınlık için)."""
    return conn.execute(
        """
        SELECT COUNT(*)                                        AS toplam,
               COUNT(*) FILTER (WHERE durum = 'basarili')      AS basarili,
               COUNT(*) FILTER (WHERE durum = 'hata')          AS hatali,
               COALESCE(ROUND(AVG(sure_ms) FILTER (WHERE durum = 'basarili')), 0) AS ort_sure_ms
        FROM api_cagrilari
        WHERE tarih > now() - INTERVAL '24 hours'
        """
    ).fetchone()
