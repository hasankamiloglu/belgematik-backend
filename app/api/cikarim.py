"""
cikarim.py - Şema ve belge işleme API uçları (Hafta 7).

    GET    /api/semalar                 -> kullanabileceğim şemalar (sistem + kendi) ve alanları
    POST   /api/semalar                 -> kendi şemamı tanımla
    DELETE /api/semalar/<id>            -> kendi şemamı sil
    POST   /api/belgeler/<id>/isle      -> OCR + alan eşleme + doğrulama, gövde: {"sema_id": 1}
    GET    /api/belgeler/<id>/cikarim   -> son işleme sonucu

Hepsi giriş gerektirir. Kullanıcı id'si token'dan alınır (sahiplik).
"""

from flask import Blueprint, current_app, g, jsonify, request

from app.api.yetki import giris_gerekli
from app.services import cikarim_servisi
from app.services.belge_servisi import BelgeHatasi
from app.services.cikarim_servisi import CikarimHatasi

cikarim_bp = Blueprint("cikarim", __name__)


@cikarim_bp.errorhandler(CikarimHatasi)
def cikarim_hatasi(h):
    govde = {"hata": h.mesaj}
    if h.ayrintilar:
        govde["ayrintilar"] = h.ayrintilar
    return jsonify(govde), h.durum_kodu


@cikarim_bp.errorhandler(BelgeHatasi)
def belge_hatasi(h):
    """Belge bulunamadı (başkasının belgesi) gibi Hafta 6 hataları."""
    return jsonify({"hata": h.mesaj}), h.durum_kodu


# ------------------------------------------------------------------ şemalar
@cikarim_bp.route("/semalar", methods=["GET"])
@giris_gerekli
def semalar():
    return jsonify({"semalar": cikarim_servisi.semalari_listele(g.kullanici["id"])})


@cikarim_bp.route("/semalar", methods=["POST"])
@giris_gerekli
def sema_olustur():
    veri = request.get_json(silent=True) or {}
    sema = cikarim_servisi.sema_olustur(g.kullanici["id"], veri)
    return jsonify({"sema": sema}), 201


@cikarim_bp.route("/semalar/<int:sema_id>", methods=["DELETE"])
@giris_gerekli
def sema_sil(sema_id):
    cikarim_servisi.sema_sil(g.kullanici["id"], sema_id)
    return jsonify({"mesaj": "Şema silindi."})


# ------------------------------------------------------------- belge işle
@cikarim_bp.route("/belgeler/<int:belge_id>/isle", methods=["POST"])
@giris_gerekli
def isle(belge_id):
    """Belgeyi seçilen şemayla işler. Gövde: {"sema_id": 1}"""
    veri = request.get_json(silent=True) or {}
    sema_id = veri.get("sema_id")
    if not isinstance(sema_id, int):
        return jsonify({"hata": "sema_id (sayı) gönderilmeli."}), 400
    sonuc = cikarim_servisi.belge_isle(
        g.kullanici["id"], belge_id, sema_id, current_app.config["UPLOAD_FOLDER"]
    )
    return jsonify(sonuc), 201


@cikarim_bp.route("/belgeler/<int:belge_id>/cikarim", methods=["GET"])
@giris_gerekli
def cikarim_sonucu(belge_id):
    return jsonify(cikarim_servisi.sonuc(g.kullanici["id"], belge_id))
