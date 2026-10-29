"""
app paketi - Belgematik BACKEND uygulaması.

Bu depo SADECE backend'dir: HTML sayfa göstermez, JSON veri döndüren bir API'dir.
Kullanıcının gördüğü ekranlar ayrı depodadır: belgematik-frontend (React).

KATMANLI MİMARİ (3 katman):
    app/api/       -> SUNUM katmanı : API uçları (URL'ler), JSON cevaplar
    app/services/  -> İŞ katmanı    : OCR, alan eşleme, doğrulama, dışa aktarma
    app/data/      -> VERİ katmanı  : Veritabanı modelleri ve veri erişimi

Kural: Her katman sadece BİR ALTINDAKİ katmanla konuşur.
    API -> İş -> Veri
API katmanı veritabanına DOĞRUDAN erişmez.
"""

import os

from flask import Flask, request

from config import VARSAYILAN_GIZLI_ANAHTAR, config_by_name


def create_app(config_name=None):
    """
    Flask uygulamasını oluşturur ve yapılandırır (Application Factory).

    Parametre:
        config_name -> "development", "testing" veya "production".
                       Verilmezse .env içindeki FLASK_ENV okunur,
                       o da yoksa "development" kullanılır.
    Döndürür:
        Hazır Flask uygulama nesnesi.
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)

    # Seçilen ortamın ayarlarını uygulamaya yükle.
    app.config.from_object(config_by_name[config_name])

    # GÜVENLİK: Canlıda SECRET_KEY varsayılan değerde kalırsa herkes sahte token
    # imzalayabilir. Bu yüzden canlı ortamda varsayılan anahtarla BAŞLAMAYI REDDET.
    if config_name == "production" and app.config["SECRET_KEY"] == VARSAYILAN_GIZLI_ANAHTAR:
        raise RuntimeError("Canlı ortamda .env içine güçlü bir SECRET_KEY yazılmalı!")

    # uploads klasörü yoksa oluştur (exist_ok=True -> varsa hata verme).
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # JSON cevaplarda Türkçe karakterler (ş, ğ, ı) ş gibi kodlanmasın, düz yazılsın.
    app.json.ensure_ascii = False

    # Blueprint -> URL'leri gruplara bölmemizi sağlayan Flask yapısı.
    # url_prefix="/api" -> bu gruptaki tüm adreslerin başına /api eklenir.
    #   Örnek: @api_bp.route("/saglik")  ==>  http://127.0.0.1:5000/api/saglik
    from app.api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # Hafta 5: kimlik doğrulama ve yönetici uçları (app/api/kimlik.py)
    #   /api/auth/kayit, /api/auth/giris, /api/auth/ben, /api/auth/cikis
    #   /api/yonetici/kullanicilar  (sadece yönetici)
    from app.api.kimlik import kimlik_bp, yonetici_bp

    app.register_blueprint(kimlik_bp, url_prefix="/api/auth")
    app.register_blueprint(yonetici_bp, url_prefix="/api/yonetici")

    # Hafta 6: belge yükleme ve ön işleme (app/api/belgeler.py)
    from app.api.belgeler import belge_bp

    app.register_blueprint(belge_bp, url_prefix="/api/belgeler")

    # 10 MB'tan büyük dosya gelirse Flask isteği daha okumadan 413 hatası verir
    # (config.py -> MAX_CONTENT_LENGTH). Bu hatayı da JSON olarak döndürüyoruz.
    @app.errorhandler(413)
    def cok_buyuk(_hata):
        return {"hata": "Dosya 10 MB'tan büyük olamaz."}, 413

    @app.route("/")
    def ana_sayfa():
        """
        Backend'in ana adresi. Sayfa göstermez; nereye bakılacağını söyler.
        Ekranlar React frontend'dedir: http://localhost:5173
        """
        return {
            "mesaj": "Belgematik backend API çalışıyor. Ekranlar için frontend'i açın.",
            "frontend": "http://localhost:5173",
            "api": ["/api/saglik", "/api/moduller", "/api/auth/giris", "/api/auth/kayit",
                    "/api/belgeler"],
        }

    # ------------------------------------------------------------------
    # CORS (Cross-Origin Resource Sharing / Kaynaklar Arası Paylaşım)
    # ------------------------------------------------------------------
    # Frontend (React) http://localhost:5173 adresinde, backend ise
    # http://127.0.0.1:5000 adresinde çalışır. Adresler farklı olduğu için
    # tarayıcı güvenlik nedeniyle isteği ENGELLER. Backend, cevabına
    # "bu adrese izin veriyorum" başlığını ekleyerek engeli kaldırır.
    # İzin verilen adresler config.py'deki CORS_ORIGINS listesindedir.
    @app.after_request
    def cors_basliklarini_ekle(response):
        # after_request -> her cevap tarayıcıya gitmeden HEMEN ÖNCE çalışır.
        origin = request.headers.get("Origin")
        if origin in app.config["CORS_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response

    return app
