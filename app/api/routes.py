"""
routes.py - API uçları (endpoints).

Her fonksiyon bir adrese bağlıdır ve JSON döndürür.
Tüm adreslerin başında /api vardır (bkz. app/__init__.py -> url_prefix).

    GET /api/          -> API hakkında kısa bilgi
    GET /api/saglik    -> Sağlık kontrolü (sunucu ayakta mı?)
    GET /api/moduller  -> Modüllerin geliştirme durumu (frontend ana sayfası kullanır)

Kimlik doğrulama uçları ayrı dosyadadır: app/api/kimlik.py (Hafta 5)
Belge yükleme uçları ayrı dosyadadır:     app/api/belgeler.py (Hafta 6)

"""

from flask import Blueprint, jsonify

# Blueprint("api", __name__) -> "api" adında bir URL grubu oluşturur.
api_bp = Blueprint("api", __name__)

# Uygulamanın sürüm numarası. Sağlık kontrolünde döndürülür.
SURUM = "0.5.0"

# Ana modüller listesi: frontend bunu ana sayfada yol haritası olarak gösterir.
# durum -> "hazir" (tamamlandı) veya "planli" (ileriki haftalarda)
MODULLER = [
    {"ad": "Proje iskeleti ve mimari", "hafta": 3, "durum": "hazir"},
    {"ad": "Veritabanı ve veri erişim katmanı", "hafta": 4, "durum": "hazir"},
    {"ad": "Kullanıcı yönetimi ve kimlik doğrulama", "hafta": 5, "durum": "hazir"},
    {"ad": "Fotoğraf yükleme ve ön işleme", "hafta": 6, "durum": "hazir"},
    {"ad": "OCR / metin çıkarma", "hafta": 7, "durum": "planli"},
    {"ad": "Alan eşleme ve doğrulama", "hafta": 8, "durum": "planli"},
    {"ad": "Yapılandırılmış çıktı (JSON)", "hafta": 9, "durum": "planli"},
    {"ad": "Düzeltme arayüzü", "hafta": 10, "durum": "planli"},
    {"ad": "Dışa aktarma (Excel/CSV/JSON)", "hafta": 11, "durum": "planli"},
]


@api_bp.route("/")
def bilgi():
    """API'nin kendini tanıttığı adres. Tarayıcıdan açınca neyin çalıştığı görülür."""
    return jsonify({
        "uygulama": "Belgematik API",
        "surum": SURUM,
        "adresler": ["/api/saglik", "/api/moduller", "/api/auth/kayit", "/api/auth/giris",
                     "/api/auth/ben", "/api/auth/cikis", "/api/yonetici/kullanicilar",
                     "/api/belgeler"],
    })


@api_bp.route("/saglik")
def saglik():
    """
    Sağlık kontrolü (health check).
    Canlı sunucu (Render vb.) ve frontend bu adrese istek atarak
    backend'in ayakta olup olmadığını kontrol eder.
    200 = her şey yolunda.
    """
    return jsonify({"durum": "calisiyor", "uygulama": "Belgematik", "surum": SURUM}), 200


@api_bp.route("/moduller")
def moduller():
    """
    Modül listesini döndürür.
    jsonify() -> Python listesini/sözlüğünü JSON formatına çevirir ve
                 "Content-Type: application/json" başlığıyla gönderir.
    """
    return jsonify(MODULLER)
