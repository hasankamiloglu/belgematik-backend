# Hafta 5 – Kullanıcı Yönetimi ve Kimlik Doğrulama

**Geliştirilen modül:** Kimlik doğrulama ve kullanıcı/rol

## Yapılan teknik çalışmalar

- [x] **Kayıt / giriş akışı:** `POST /api/auth/kayit`, `POST /api/auth/giris`, `GET /api/auth/ben`, `POST /api/auth/cikis`
- [x] **Parola hash'leme:** PBKDF2-SHA256 + rastgele tuz, 600.000 tekrar (`app/services/auth/parola.py`)
- [x] **Token yönetimi:** JWT (60 dk), çıkışta sunucu tarafında geçersiz kılma (`token_surumu`)
- [x] **Rol tabanlı erişim:** `@giris_gerekli`, `@yetki_gerekli("yonetici")` (`app/api/yetki.py`)
- [x] **Başarısız giriş koruması:** genel hata mesajı, 5 denemede 15 dk kilit, giriş günlüğü
- [x] Migration `003_kimlik_dogrulama.sql`: `yetki`, `basarisiz_giris`, `kilit_bitis`, `son_giris`, `token_surumu` + `giris_denemeleri` tablosu
- [x] Yönetici atama komutu: `python manage.py yonetici EMAIL`
- [x] **React:** Giriş, Kayıt, Panelim, Yönetici sayfaları; `KorumaliSayfa`, oturum zamanlayıcısı, otomatik çıkış
- [x] 26 yeni test (toplam 41)

## Teslim edilen çıktılar

| Çıktı | Konum |
|---|---|
| Çalışan kayıt/giriş | Backend `app/api/kimlik.py`, `app/services/auth/` · Frontend `src/pages/` |
| Rol tabanlı erişim | `app/api/yetki.py`, `/api/yonetici/kullanicilar` · Frontend `KorumaliSayfa.jsx` |
| Kısa güvenlik notu | `docs/guvenlik-notu.md` |
| Testler | `tests/test_parola_token.py`, `tests/test_kimlik.py` |

## Gösterilecek ilerleme (demo sırası)

1. Giriş yapmadan `#/panel` aç → giriş sayfasına yönlendirilir
2. Kayıt ol → zayıf parolada kurallar listelenir
3. Yanlış parola → "E-posta veya parola hatalı."
4. Doğru giriş → Panelim
5. `#/yonetici` → **403 Erişim yetkiniz yok**
6. Çıkış → `yonetici@ornek.test` ile giriş → Yönetici paneli (kullanıcılar + giriş denemeleri)
7. pgAdmin → `kullanicilar.sifre_hash` → düz parola yok
8. `pytest` → 41 test geçiyor

## Kontrol kriterleri

| Kriter | Kanıt |
|---|---|
| Parola düz metin saklanmıyor | pgAdmin `sifre_hash`, `test_parola_duz_metin_saklanmiyor`, `test_kayit_basarili_ve_parola_hashli` |
| Yetkisiz erişim engelleniyor | `test_tokensiz_korumali_uca_erisilemez` (401), `test_normal_kullanici_yonetici_sayfasina_giremez` (403) |
| Oturum/token doğru yönetiliyor | `test_suresi_dolmus_token_reddedilir`, `test_icerigi_degistirilen_token_reddedilir`, `test_cikistan_sonra_eski_token_gecersiz` |

## Yapay zekâ kullanımı

Yapay zekâ; parola hash yöntemlerini (bcrypt, PBKDF2, Argon2) karşılaştırmak, oturum ve JWT farkını
araştırmak ve OWASP'ın kimlik doğrulama önerilerini (genel hata mesajı, hesap kilitleme, token süresi)
derlemek için kullanıldı.

## Öğrencinin kendi geliştirdiği bölümler

- Parola hash ve doğrulama akışı: tuz üretimi, tekrar sayısı, sabit süreli karşılaştırma (`parola.py`)
- Rol kontrolü: `@yetki_gerekli("yonetici")` dekoratörü ve `/api/yonetici/kullanicilar` ucu

## Sık yapılan hatalara karşı

| Hata | Bu projede |
|---|---|
| Parolayı düz metin saklamak | Tuzlu PBKDF2 hash |
| Yetkilendirmeyi yalnızca arayüzde yapmak | Backend dekoratörleri. Frontend sadece görüntü |
| Oturum süresini yönetmemek | 60 dk `exp`, otomatik çıkış, sunucu tarafı çıkış |
