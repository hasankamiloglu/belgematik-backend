"""
kimlik.py - Kimlik doğrulama ve yönetici API uçları (Hafta 5).

    POST /api/auth/kayit          -> yeni hesap         (herkese açık)
    POST /api/auth/giris          -> giriş, token alır  (herkese açık)
    GET  /api/auth/ben            -> giriş yapan kişi   (giriş gerekli)
    POST /api/auth/cikis          -> çıkış              (giriş gerekli)
    GET  /api/yonetici/kullanicilar -> kullanıcı listesi (SADECE yönetici)

Bu dosya iş kuralı içermez: isteği okur, servisi çağırır, JSON cevap döndürür.
"""

from flask import Blueprint, current_app, g, jsonify, request

from app.api.yetki import giris_gerekli, yetki_gerekli
from app.services.auth import kimlik_servisi
from app.services.auth.kimlik_servisi import KimlikHatasi

kimlik_bp = Blueprint("kimlik", __name__)
yonetici_bp = Blueprint("yonetici", __name__)


@kimlik_bp.errorhandler(KimlikHatasi)
def kimlik_hatasi(h):
    """
    Servisten gelen KimlikHatasi'nı JSON hata cevabına çevirir.
    errorhandler -> bu blueprint'teki herhangi bir uçta bu hata olursa burası çalışır.
    """
    govde = {"hata": h.mesaj}
    if h.ayrintilar:
        govde["ayrintilar"] = h.ayrintilar
    return jsonify(govde), h.durum_kodu


def _govde():
    """
    İstekteki JSON gövdeyi sözlük olarak döndürür.
    silent=True -> JSON bozuksa hata verme, None döndür; o zaman boş sözlük kullan.
    """
    return request.get_json(silent=True) or {}


@kimlik_bp.route("/kayit", methods=["POST"])
def kayit():
    """Beklenen gövde: {"ad_soyad", "email", "parola", "rol"}  ->  201 Created"""
    veri = _govde()
    kullanici = kimlik_servisi.kayit_ol(
        veri.get("ad_soyad"), veri.get("email"), veri.get("parola"),
        veri.get("rol", "bireysel"),
    )
    return jsonify({"mesaj": "Kayıt başarılı. Şimdi giriş yapabilirsiniz.", "kullanici": kullanici}), 201


@kimlik_bp.route("/giris", methods=["POST"])
def giris():
    """Beklenen gövde: {"email", "parola"}  ->  200 + token"""
    veri = _govde()
    ayar = current_app.config
    sonuc = kimlik_servisi.giris_yap(
        veri.get("email"), veri.get("parola"),
        ip_adresi=request.remote_addr,          # isteğin geldiği IP (günlük için)
        gizli_anahtar=ayar["SECRET_KEY"],
        sure_dakika=ayar["TOKEN_SURESI_DAKIKA"],
        deneme_siniri=ayar["GIRIS_DENEME_SINIRI"],
        kilit_dakika=ayar["HESAP_KILIT_DAKIKA"],
    )
    return jsonify(sonuc), 200


@kimlik_bp.route("/ben", methods=["GET"])
@giris_gerekli
def ben():
    """Token sahibinin bilgileri. g.kullanici'yi @giris_gerekli doldurdu."""
    return jsonify({"kullanici": g.kullanici})


@kimlik_bp.route("/cikis", methods=["POST"])
@giris_gerekli
def cikis():
    """Çıkış: sunucu tarafında token sürümü artar, eski token bir daha çalışmaz."""
    kimlik_servisi.cikis_yap(g.kullanici["id"])
    return jsonify({"mesaj": "Çıkış yapıldı."})


# ---------------------------------------------------------------- YÖNETİCİ
@yonetici_bp.route("/kullanicilar", methods=["GET"])
@yetki_gerekli("yonetici")  # ROL TABANLI ERİŞİM: sadece yönetici
def kullanicilar():
    """Tüm kullanıcılar ve son giriş denemeleri (yönetici paneli)."""
    return jsonify(kimlik_servisi.yonetici_ozeti())
