# Hafta 7 – Çekirdek Modül B: Alan Eşleme ve Doğrulama + Entegrasyon

**Geliştirilen modül:** Alan Eşleme ve Doğrulama

## Yapılan teknik çalışmalar

- [x] **Şema tanımı:** `GET/POST/DELETE /api/semalar`; sistem + kullanıcı şemaları, alan tipi, zorunluluk, anahtar kelime, regex
- [x] **OCR:** Tesseract ile ön işlenmiş görselden metin ve okuma güveni (`app/services/ocr/tesseract.py`)
- [x] **Alan eşleme:** anahtar kelime → kalıp → konum yöntemleri, eleyici kelimeler, Türk para/tarih biçimi (`app/services/extraction/`)
- [x] **Doğrulama kuralları:** zorunlu, tip, regex, VKN/TCKN kontrol hanesi, KDV oranı, e-posta/telefon + iş kuralları: KDV hesabı, matrah + KDV = toplam (`app/services/validation/`)
- [x] **Entegrasyon:** `POST /api/belgeler/<id>/isle` → OCR → eşleme → doğrulama → tek transaction'da kayıt, belge `islendi`
- [x] Migration `005_alan_esleme_dogrulama.sql`, örnek veriye anahtar kelimeler
- [x] **React:** "Verileri çıkar" penceresi (alan tablosu, güven, ✓/✗, iş kuralları, ham metin), Şemalar sayfası
- [x] `python manage.py ocr-kontrol` komutu, sentetik örnek belgeler (`tests/ornek_belgeler.py`)
- [x] 36 yeni test (toplam 97)

## Teslim edilen çıktılar

| Çıktı | Konum |
|---|---|
| Çalışan alan eşleme ve doğrulama | `app/services/extraction/`, `app/services/validation/`, `app/services/cikarim_servisi.py`, `app/api/cikarim.py` · Frontend `CikarimPenceresi.jsx`, `SemalarSayfasi.jsx` |
| İlgili kod | yukarıdakiler + `db/migrations/005_alan_esleme_dogrulama.sql`, `app/data/repositories/sema_repo.py` |
| Kısa açıklama | `docs/alan-esleme.md` |
| Testler | `tests/test_eslesme_dogrulama.py` (veritabanı ve OCR gerektirmez), `tests/test_cikarim.py` |

## Gösterilecek ilerleme (demo sırası)

1. `muhasebeci@ornek.test` ile giriş yap. `ornek-belgeler` klasöründen 5 belgeyi yükle.
2. `fis_dogru` → Verileri çıkar (fis): ✓ tüm alanlar ve kurallar doğrulandı
3. `fis_kdv_hatali`: ✗ "Hesaplanan KDV 15.00, okunan 25.00"
4. `fis_vkn_hatali`: ✗ "Vergi numarasının kontrol hanesi tutmuyor"
5. `fatura` (fatura şeması): ✓ Matrah + KDV = Toplam
6. `kartvizit` (kartvizit şeması): ad, firma, telefon, e-posta
7. Şemalar → yeni şema tanımla. Hatalı alan adı girilince red, düzeltince kayıt.
8. `pytest` → 97 test

## Kontrol kriterleri

| Kriter | Kanıt |
|---|---|
| Alan eşleme ve doğrulama çalışıyor | `test_fis_alanlari_eslenir`, `test_dogru_fis_islenir_ve_dogrulanir`, `test_kartvizit_kalip_ile` |
| Doğrulama ve iş kuralları uygulanıyor | `test_vkn_ve_tckn_kontrol_hanesi`, `test_alan_kurallari`, `test_kdv_orani_ile_tutari_tutarli_mi`, `test_matrah_kdv_toplam`, `test_kdv_tutarsiz_fis_bekliyor_durumunda` |
| Önceki modüllerle tutarlı | Hafta 6 ön işlenmiş görsel → OCR · Hafta 5 sahiplik: `test_baskasinin_belgesi_ve_semasi_kullanilamaz` · Hafta 4 RESTRICT: `test_kullanimdaki_sema_silinemez` · eski 61 test geçiyor |

## Yapay zekâ kullanımı

Yapay zekâ; Türk fişlerindeki tipik alan düzenlerini ve anahtar kelimeleri (TOPKDV, ARA TOPLAM, V.D.),
VKN/TCKN kontrol hanesi algoritmalarını ve KDV dahil tutardan KDV hesaplama formülünü araştırmak,
ayrıca eşleyiciyi "yöntem sırası + eleyici kelime" yapısına çevirmek (refaktör) için kullanıldı.

## Öğrencinin kendi geliştirdiği bölümler

- Çekirdek mantık: alan eşleyici (`eslestirici.py`), yöntem sırası ve güven puanları
- İş kuralları ve doğrulama: KDV hesabı, matrah + KDV = toplam, vergi no kontrol hanesi (`dogrulayici.py`, `kimlik_no.py`)

## Sık yapılan hatalara karşı

| Hata | Bu projede |
|---|---|
| Doğrulamayı atlamak | Her çıkarım iki seviyede doğrulanıyor; sorun varsa durum `bekliyor` |
| Erişim/sahiplik kontrolünü unutmak | Belge sahibi + şema sahibi kontrolü, başkasınınki 404 |
| İlişkili kayıtları yönetmemek | Çıkarım + değerler + belge durumu tek transaction; kullanımdaki şema RESTRICT ile korunuyor |
