"""
yetki.py - Korumalı API uçları için "bekçi" dekoratörleri (yetkilendirme katmanı).

Dekoratör (decorator) nedir?
    Bir fonksiyonun ÖNÜNE eklenen ve o fonksiyon çalışmadan önce kontrol yapan yapı.
    @giris_gerekli yazılan uç, token yoksa hiç çalışmaz; 401 döner.

Kullanım:
    @kimlik_bp.route("/ben")
    @giris_gerekli                      -> sadece giriş yapmış kullanıcılar
    def ben(): ...

    @yonetici_bp.route("/kullanicilar")
    @yetki_gerekli("yonetici")          -> sadece yöneticiler
    def kullanicilar(): ...

401 Unauthorized -> "Seni tanımıyorum"  (token yok / geçersiz / süresi dolmuş)
403 Forbidden    -> "Seni tanıyorum ama bu sayfaya iznin yok" (yetki yetersiz)

ÖNEMLİ: Yetki kontrolü BURADA, yani SUNUCUDA yapılır. Frontend'deki gizleme
sadece kolaylıktır; biri tarayıcıdan doğrudan API'ye istek atsa bile bu kontrol çalışır.
"""

from functools import wraps

from flask import current_app, g, jsonify, request

from app.services.auth.kimlik_servisi import KimlikHatasi, token_ile_kullanici


def _token_al():
    """
    İstek başlığındaki token'ı okur.
    Beklenen biçim:  Authorization: Bearer eyJhbGciOi...
    Token yoksa None döner.
    """
    baslik = request.headers.get("Authorization", "")
    if baslik.startswith("Bearer "):
        return baslik[len("Bearer "):].strip() or None
    return None


def giris_gerekli(fonksiyon):
    """
    Giriş yapmamış kullanıcıyı durdurur (401).
    Geçerliyse kullanıcı bilgisi  g.kullanici  içine konur;
    uç fonksiyonu bu bilgiyi oradan okur.
    (g -> Flask'ın "bu isteğe özel" geçici hafızası)
    """

    @wraps(fonksiyon)  # orijinal fonksiyonun adını korur (Flask bunu ister)
    def sarmalayici(*args, **kwargs):
        token = _token_al()
        if token is None:
            return jsonify({"hata": "Bu işlem için giriş yapmalısınız."}), 401
        try:
            g.kullanici = token_ile_kullanici(token, current_app.config["SECRET_KEY"])
        except KimlikHatasi as h:
            return jsonify({"hata": h.mesaj}), h.durum_kodu
        return fonksiyon(*args, **kwargs)

    return sarmalayici


def yetki_gerekli(*izinli_yetkiler):
    """
    Rol tabanlı erişim: sadece listedeki yetkilere izin verir.
    Örnek: @yetki_gerekli("yonetici")

    Önce giriş kontrolü (401), sonra yetki kontrolü (403) yapılır.
    """

    def dekorator(fonksiyon):
        @wraps(fonksiyon)
        @giris_gerekli  # önce: giriş yapmış mı?
        def sarmalayici(*args, **kwargs):
            # sonra: yetkisi yeterli mi?
            if g.kullanici["yetki"] not in izinli_yetkiler:
                return jsonify({"hata": "Bu sayfaya erişim yetkiniz yok."}), 403
            return fonksiyon(*args, **kwargs)

        return sarmalayici

    return dekorator
