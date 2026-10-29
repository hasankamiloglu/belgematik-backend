"""
belgeler.py - Belge yükleme ve görüntüleme API uçları (Hafta 6).

    POST   /api/belgeler                  -> dosya yükle + ön işle (multipart/form-data, alan adı: "dosya")
    GET    /api/belgeler                  -> kendi belgelerim + kalan kredi
    GET    /api/belgeler/<id>             -> tek belgenin bilgisi
    GET    /api/belgeler/<id>/gorsel?tur= -> görsel dosyası (orijinal / islenmis / kucuk)
    DELETE /api/belgeler/<id>             -> belgeyi sil

HEPSİ giriş gerektirir (@giris_gerekli). Kullanıcı id'si İSTEKTEN değil TOKEN'dan
alınır (g.kullanici["id"]); böylece kimse başkası adına belge yükleyemez/göremez.
"""

import io
import mimetypes

from flask import Blueprint, current_app, g, jsonify, request, send_file

from app.api.yetki import giris_gerekli
from app.services import belge_servisi
from app.services.belge_servisi import BelgeHatasi

belge_bp = Blueprint("belgeler", __name__)


@belge_bp.errorhandler(BelgeHatasi)
def belge_hatasi(h):
    """Servisten gelen BelgeHatasi'nı JSON hata cevabına çevirir."""
    return jsonify({"hata": h.mesaj}), h.durum_kodu


def _klasor():
    """Yüklenen dosyaların klasörü (config.py -> UPLOAD_FOLDER)."""
    return current_app.config["UPLOAD_FOLDER"]


@belge_bp.route("", methods=["POST"])
@giris_gerekli
def yukle():
    """
    Dosya yükleme. Tarayıcı dosyayı "multipart/form-data" biçiminde gönderir.
    request.files["dosya"] -> yüklenen dosya nesnesi
        .filename -> kullanıcının bilgisayarındaki dosya adı
        .read()   -> dosyanın baytları
    """
    dosya = request.files.get("dosya")
    if dosya is None or not dosya.filename:
        return jsonify({"hata": "Dosya seçilmedi. Alan adı 'dosya' olmalı."}), 400

    sonuc = belge_servisi.yukle(g.kullanici["id"], dosya.filename, dosya.read(), _klasor())
    return jsonify(sonuc), 201


@belge_bp.route("", methods=["GET"])
@giris_gerekli
def listele():
    return jsonify(belge_servisi.listele(g.kullanici["id"]))


@belge_bp.route("/<int:belge_id>", methods=["GET"])
@giris_gerekli
def getir(belge_id):
    """<int:belge_id> -> adresteki sayı fonksiyona parametre olarak gelir: /api/belgeler/5 -> 5"""
    belge = belge_servisi.getir(g.kullanici["id"], belge_id)
    return jsonify({"belge": belge_servisi.disari(belge)})


@belge_bp.route("/<int:belge_id>/gorsel", methods=["GET"])
@giris_gerekli
def gorsel(belge_id):
    """
    Görsel dosyasını döndürür. ?tur=islenmis (varsayılan), orijinal veya kucuk.
    send_file -> dosyayı doğru içerik tipiyle (image/png, application/pdf...) gönderir.

    Dosyayı önce belleğe okuyup HEMEN kapatıyoruz ("with" bloğu). Windows, açık
    duran bir dosyanın silinmesine izin vermez; böylece görsel gösterilirken
    kullanıcı belgeyi silerse "dosya kullanımda" hatası çıkmaz. (Dosyalar en fazla 10 MB.)
    """
    tur = request.args.get("tur", "islenmis")  # request.args -> adresteki ?anahtar=değer kısmı
    yol = belge_servisi.gorsel_yolu(g.kullanici["id"], belge_id, tur, _klasor())
    with open(yol, "rb") as f:  # "rb" -> bayt olarak oku
        icerik = f.read()
    # mimetypes.guess_type("a.png") -> ("image/png", None): uzantıdan içerik tipini bulur
    tip = mimetypes.guess_type(yol)[0] or "application/octet-stream"
    return send_file(io.BytesIO(icerik), mimetype=tip, max_age=0)


@belge_bp.route("/<int:belge_id>", methods=["DELETE"])
@giris_gerekli
def sil(belge_id):
    belge_servisi.sil(g.kullanici["id"], belge_id, _klasor())
    return jsonify({"mesaj": "Belge silindi."})
