# Değişiklik Günlüğü (CHANGELOG) – belgematik-backend

Sürüm numaraları **Anlamsal Sürümleme (Semantic Versioning)** kuralına uyar: `MAJOR.MINOR.PATCH`

| Parça | Ne zaman artar? | Örnek |
|---|---|---|
| MAJOR | Eski kullanımı bozan büyük değişiklik (API değişti) | 1.0.0 → 2.0.0 |
| MINOR | Geriye uyumlu **yeni özellik** | 0.6.0 → 0.7.0 |
| PATCH | Sadece **hata düzeltmesi** | 0.7.0 → 0.7.1 |

`0.x` sürümleri "geliştirme aşamasında" demektir. İlk kararlı (canlıya hazır) sürüm `1.0.0` olacak.
Her sürüm GitHub'da bir **etiketle (tag)** işaretlenir: `git tag -a v0.7.0`.

---

## [0.7.0] – Hafta 8 · Ara sürüm (vize) 🏷️ `v0.7.0`
### Eklendi
- Uçtan uca entegrasyon testi: kayıt → giriş → yükleme → OCR → eşleme → doğrulama → yönetici → çıkış (`tests/test_uctan_uca.py`)
- GitHub Actions: her `git push`ta PostgreSQL + Tesseract kurup tüm testleri çalıştırır (`.github/workflows/testler.yml`)
- Yapay zekâ kullanım günlüğü, ara sürüm ilerleme raporu, demo senaryosu (`docs/`)
### Düzeltildi
- `manage.py seed` belgeleri silerken `uploads/` altındaki dosyalar diskte kalıyordu → artık temizleniyor
- (Hafta 7 sonrası) Kullanımdaki şema silinmek istenince 409 yerine 500 hatası → `RestrictViolation` yakalanıyor
- (Hafta 7 sonrası) Türkçe OCR modeli `%20` yazısını `420` okuyordu → dil sırası `eng+tur`, eşleyici `420`'yi tolere ediyor
- (Hafta 6 sonrası) Windows'ta görsel gösterilirken belge silinince "dosya kullanımda" hatası → dosya belleğe okunup kapatılıyor

## [0.6.0] – Hafta 7 · OCR, alan eşleme ve doğrulama
- Tesseract OCR, şema tanımı (`/api/semalar`), anahtar kelime/kalıp/konum ile alan eşleme
- Alan kuralları (zorunlu, tip, regex, VKN/TCKN kontrol hanesi) + iş kuralları (KDV hesabı, matrah + KDV = toplam)
- Migration 005

## [0.5.0] – Hafta 6 · Fotoğraf yükleme ve ön işleme
- Yükleme API'si, kalite ölçümü (bulanıklık, karanlık, kontrast), ön işleme (EXIF yön, gri, küçültme, kontrast, keskinleştirme)
- Kredi, tekrar yükleme yasağı (SHA-256), sahiplik kuralları · Migration 004

## [0.4.0] – Hafta 5 · Kimlik doğrulama
- Kayıt/giriş, PBKDF2 parola hash + tuz, JWT (60 dk), rol tabanlı erişim, hesap kilitleme · Migration 003

## [0.3.0] – Hafta 4 · Veritabanı
- PostgreSQL, 7 tablo, kısıtlar, indeksler, migration aracı, CRUD repository'leri, örnek veri

## [0.2.0] – Hafta 3 · Proje iskeleti
- Flask uygulama fabrikası, 3 katmanlı mimari, API + CORS, frontend/backend ayrı depolar
