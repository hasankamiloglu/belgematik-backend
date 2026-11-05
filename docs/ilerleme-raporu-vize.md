# Ara Sürüm İlerleme Raporu – v0.7.0 (Hafta 8, Vize)

**Proje:** Belgematik – Fiş, fatura ve kartvizit fotoğraflarından yapılandırılmış veri çıkarma
**Depolar:** `hasankamiloglu/belgematik-backend` · `hasankamiloglu/belgematik-frontend` — ikisi de **`v0.7.0`** etiketli

## 1. Özet

Kullanıcı kayıt olur ve giriş yapar, fiş fotoğrafını yükler. Sistem görseli kalite açısından ölçüp düzeltir, OCR ile okur, alanları şemaya eşler, kurallarla doğrular ve veritabanına kaydeder. **Bu akış uçtan uca çalışıyor** ve tek bir otomatik testle (`tests/test_uctan_uca.py`) kanıtlanıyor.

## 2. Mimari

```
React (5173)  ──HTTP/JSON + Bearer token──▶  Flask API (5000)
                                               ├─ 1) SUNUM  app/api/        kimlik, belgeler, cikarim
                                               ├─ 2) İŞ     app/services/   auth, preprocessing, ocr,
                                               │                            extraction, validation
                                               └─ 3) VERİ   app/data/       repositories (saf SQL)
                                                                 │
                                         PostgreSQL ◀────────────┘   Tesseract OCR   uploads/
```
Kural: Her katman sadece bir altındakiyle konuşur. Ayrıntılı şema: `docs/mimari-sema.png`.

## 3. Modül durumu

| Hafta | Modül | Durum | Kanıt |
|---|---|---|---|
| 3 | Proje iskeleti, mimari | ✅ | `app/`, diyagramlar |
| 4 | Veritabanı (8 tablo, 5 migration) | ✅ | `db/migrations/`, `test_veritabani.py` |
| 5 | Kimlik doğrulama ve roller | ✅ | `test_kimlik.py`, `docs/guvenlik-notu.md` |
| 6 | Yükleme ve ön işleme | ✅ | `test_belgeler.py`, `test_on_isleme.py`, `docs/on-isleme.md` |
| 7 | OCR, alan eşleme, doğrulama | ✅ | `test_eslesme_dogrulama.py`, `test_cikarim.py`, `docs/alan-esleme.md` |
| 8 | Entegrasyon, ara sürüm | ✅ | `test_uctan_uca.py`, `CHANGELOG.md`, GitHub Actions |
| 9+ | Düzeltme ekranı, dışa aktarma, canlıya alma | ⏳ | Bölüm 7 |

## 4. Sayılarla

| | |
|---|---|
| API uçları | 18 |
| Veritabanı tabloları | 8 (+ `schema_migrations`) |
| Otomatik test | **99** (birim + API + uçtan uca) |
| React sayfası | 7 (Ana, Giriş, Kayıt, Panel, Belgelerim, Şemalar, Yönetici) |
| Sürüm | v0.2 → v0.7 (6 sürüm, her hafta bir commit) |

## 5. Entegrasyon: hangi modül hangi veriyi nereden alıyor?

| Modül | Girdi (nereden) | Çıktı (nereye) |
|---|---|---|
| Kimlik (H5) | e-posta + parola (React formu) | JWT token (tarayıcı) · `kullanicilar`, `giris_denemeleri` |
| Yükleme (H6) | dosya (React) + kullanıcı (token) | orijinal/işlenmiş/küçük görsel (`uploads/<id>/`) · `belgeler` satırı · kredi −1 (`abonelikler`) |
| OCR (H7) | işlenmiş görsel (`belgeler.islenmis_yol`) | ham metin + okuma güveni |
| Eşleme (H7) | ham metin + şema alanları (`sema_alanlari`) | {alan: değer, güven, yöntem} |
| Doğrulama (H7) | eşleme sonucu + şema kuralları | geçerli mi, hata mesajı, iş kuralı sonuçları |
| Kayıt (H4/H7) | hepsi | `cikarim_kayitlari` + `cikarim_degerleri` (N-N), `belgeler.durum = islendi` — tek transaction |

## 6. Giderilen hatalar (bu sürüm)

| Hata | Çözüm |
|---|---|
| Windows'ta görsel gösterilirken belge silinemiyordu | Dosya belleğe okunup hemen kapatılıyor |
| Kullanımdaki şema silinince 409 yerine 500 hatası | PostgreSQL `RestrictViolation` hatası yakalanıyor |
| Türkçe OCR modeli "%20" → "420" okuyordu | Dil sırası `eng+tur` (4 yazı tipi × 5 belgede 4 hata → 0), eşleyici `420`'yi tolere ediyor |
| `seed` sonrası `uploads/` altında sahipsiz dosyalar kalıyordu | `seed` kullanıcı klasörlerini de temizliyor |
| Panelim'de kredi bilgisi eski kalıyordu | Sayfa açılınca güncel bilgi alınıyor |
| "Çıkış yapıldı" mesajı sonradan ilgisiz yerde görünüyordu | Ana sayfa veya kayıt sayfasına geçince siliniyor |

## 7. Bilinen sınırlar ve sonraki plan

| Sonraki adım | Neden |
|---|---|
| **Düzeltme ekranı:** yanlış okunan alanı düzelt → yeniden doğrula | Doğrulama sorun bulunca kullanıcı müdahale edebilmeli (`deger_duzelt` hazır) |
| **Dışa aktarma:** Excel / CSV / JSON | Muhasebecinin asıl ihtiyacı |
| PDF'ten görsel üretip OCR'a sokma | Şimdilik PDF sadece saklanıyor |
| Yapay zekâ OCR motoru ("pro" paket) | Karmaşık faturalarda kural tabanlı eşleme yetersiz kalabilir |
| Canlıya alma (Render + Vercel), HTTPS, istek sınırlama | Proje hedefi: canlı ürün |

## 8. Demo senaryosu (5 dakika)

| # | Ne yapılır | Ne söylenir |
|---|---|---|
| 1 | GitHub → Tags → `v0.7.0`, Actions → yeşil ✓ | "Ara sürüm etiketli; her push'ta 99 test otomatik çalışıyor." |
| 2 | Yeni kullanıcı kaydı → giriş | "Parola tuzlu hash ile saklanıyor, giriş JWT token veriyor." |
| 3 | `fis_dogru.jpg` yükle → kalite 100, kredi 19 | "Görsel ölçülüp OCR için düzeltildi, 1 kredi düştü." |
| 4 | Verileri çıkar (fis) → ✓ | "OCR okudu, eşleyici alanları buldu, kurallar doğruladı." |
| 5 | `fis_kdv_hatali.jpg` → ⚠ KDV kuralı | "Alanlar tek tek doğru ama birbiriyle çelişiyor; iş kuralı yakaladı." |
| 6 | Yönetici ile giriş → yeni kullanıcı listede | "Rol tabanlı erişim; normal kullanıcı bu sayfayı göremez." |
| 7 | Terminal: `pytest` → 99 passed | "Uçtan uca test bu senaryonun aynısını otomatik yapıyor." |
