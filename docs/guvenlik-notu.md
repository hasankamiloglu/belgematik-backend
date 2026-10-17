# Güvenlik Notu – Kimlik Doğrulama ve Yetkilendirme (Hafta 5)

## 1. Kavramlar

| Kavram | Soru | Belgematik'te |
|---|---|---|
| **Kimlik doğrulama** (authentication) | "Sen kimsin?" | E-posta + parola → token |
| **Yetkilendirme** (authorization) | "Buna iznin var mı?" | `yetki`: `kullanici` / `yonetici` |

`rol` (bireysel / kobi / muhasebeci) hesap **türüdür** (paket, kredi). Erişim kontrolü **`yetki`** kolonuyla yapılır.

## 2. Parola saklama

- Parola **asla düz metin saklanmaz**. `kullanicilar.sifre_hash` kolonunda şu biçimde tutulur:
  `pbkdf2_sha256$600000$<tuz>$<hash>`
- **Algoritma:** PBKDF2-HMAC-SHA256, **600.000 tekrar** (OWASP önerisi). Bilerek yavaştır; kaba kuvvet denemelerini yavaşlatır.
- **Tuz (salt):** Her kullanıcıya 16 baytlık rastgele değer (`secrets.token_hex`). Aynı parolanın hash'leri farklı olur, hazır hash tabloları (rainbow table) işe yaramaz.
- **Karşılaştırma:** `hmac.compare_digest` ile sabit sürede (zamanlama saldırısına karşı).
- **Parola kuralı:** en az 8 karakter, en az bir harf ve bir rakam (backend'de zorunlu, frontend'de sadece bilgi).
- Kod: `app/services/auth/parola.py`. bcrypt yerine Python'un yerleşik `hashlib` modülü seçildi: ek kurulum gerekmiyor ve tuz/tekrar adımları kodda açıkça görülüyor.

## 3. Oturum / token yönetimi

- Giriş başarılıysa backend **JWT** üretir (HS256, `SECRET_KEY` ile imzalı). İçerik: kullanıcı id, yetki, token sürümü, `exp`.
- **Süre:** 60 dakika (`TOKEN_SURESI_DAKIKA`). Süre dolunca backend 401 döner; frontend zamanlayıcısı da kullanıcıyı otomatik çıkarır.
- **Çıkış:** `POST /api/auth/cikis` kullanıcının `token_surumu` değerini artırır. Eski token çalınmış olsa bile artık geçersizdir.
- **Her istekte kontrol:** İmza, süre, kullanıcının hâlâ var olup olmadığı ve token sürümü kontrol edilir. Yetki değişirse eski token'lar geçersiz olur.
- Değiştirilmiş token (ör. `"yetki": "yonetici"` yazılmış) imza tutmadığı için reddedilir. Sadece `HS256` kabul edilir, `alg: none` hilesi çalışmaz.
- Canlı ortamda varsayılan `SECRET_KEY` ile uygulama **başlamaz**.

## 4. Başarısız giriş

- Yanlış parola ve olmayan e-posta için **aynı mesaj** verilir: "E-posta veya parola hatalı." Böylece hangi e-postaların kayıtlı olduğu öğrenilemez. Olmayan e-postada da hash hesaplanır, cevap süresi eşit kalır.
- **5 hatalı denemede hesap 15 dakika kilitlenir** (HTTP 429). Kilitliyken doğru parola da kabul edilmez.
- Her deneme `giris_denemeleri` tablosuna yazılır (e-posta, sonuç, IP, zaman). Parola yazılmaz. Yönetici panelinde görünür.

## 5. Rol tabanlı erişim

| Uç | Koruma | Yetkisiz durumda |
|---|---|---|
| `POST /api/auth/kayit`, `/giris` | Herkese açık | – |
| `GET /api/auth/ben`, `POST /api/auth/cikis` | `@giris_gerekli` | 401 |
| `GET /api/yonetici/kullanicilar` | `@yetki_gerekli("yonetici")` | 401 (giriş yok) / 403 (yetki yok) |

- Kontrol **sunucuda** (dekoratörlerde) yapılır. Frontend'deki `KorumaliSayfa` sadece kullanıcı deneyimi içindir; atlatılsa bile API veri vermez.
- Kayıtta gönderilen `yetki` alanı **yok sayılır** (kimse kendini yönetici yapamaz). Yönetici sadece sunucudan atanır: `python manage.py yonetici EMAIL`.
- Cevaplarda `sifre_hash` gibi alanlar hiçbir zaman yer almaz (`guvenli_bilgi` fonksiyonu).

## 6. OWASP ile ilişki

| OWASP Top 10 (2021) | Alınan önlem |
|---|---|
| A01 Bozuk Erişim Kontrolü | Sunucu tarafı rol kontrolü, 401/403 ayrımı |
| A02 Kriptografik Hatalar | Tuzlu, yavaş hash; gizli anahtar `.env`'de |
| A03 Enjeksiyon | Parametreli SQL (`%s`) |
| A07 Kimlik Doğrulama Hataları | Parola kuralı, hesap kilitleme, genel hata mesajı, token süresi |
| A09 Günlükleme Eksikliği | `giris_denemeleri` tablosu |

## 7. Bilinen sınırlar (sonraki adımlar)

- Token tarayıcıda `localStorage`'da tutuluyor. Sitede XSS açığı olursa okunabilir. İleride `HttpOnly` çerez + CSRF koruması düşünülebilir.
- Kilitleme hesap bazlı. IP bazlı istek sınırlama (rate limiting) canlıya geçerken eklenecek.
- Canlıda **HTTPS** zorunlu olacak (token ağda düz metin gitmesin).
- Örnek veri hesaplarının parolası (`Deneme123`) sadece geliştirme içindir. Canlıda `seed` çalıştırılmaz.
