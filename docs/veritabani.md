# Veritabanı (PostgreSQL)

## Yaklaşım: Saf SQL + migration

| Parça | Dosya | İçerik |
|---|---|---|
| Şema (DDL) | `db/migrations/001_tablolari_olustur.sql` | 7 tablo, birincil/yabancı anahtarlar, CHECK/UNIQUE/NOT NULL kısıtları |
| İndeksler | `db/migrations/002_indeksleri_olustur.sql` | 5 indeks + eklenmeyenlerin gerekçesi |
| Kimlik (Hafta 5) | `db/migrations/003_kimlik_dogrulama.sql` | yetki, hatalı giriş sayacı, kilit, token sürümü + `giris_denemeleri` tablosu |
| Ön işleme (Hafta 6) | `db/migrations/004_belge_on_isleme.sql` | `belgeler`: hash, işlenmiş yol, boyut, kalite puanı/uyarıları, `on_islendi` durumu, tekrar yükleme UNIQUE'i |
| Örnek veri (DML) | `db/seed/ornek_veri.sql` | Tamamen sentetik veri (KVKK uyumlu) |
| Örnek sorgular | `db/sorgular/ornek_sorgular.sql` | JOIN, GROUP BY, N-N sorgusu, EXPLAIN |
| Bağlantı | `app/data/db.py` | `DATABASE_URL` ile psycopg bağlantısı |
| Migration aracı | `app/data/migrate.py` | Dosyaları sırayla, bir kez ve transaction içinde uygular |
| CRUD | `app/data/repositories/*.py` | Parametreli SQL ile ekle / oku / güncelle / sil |

**Neden ORM değil?** Hangi SQL'in çalıştığı açıkça görünsün; indeks, kısıt ve transaction
kavramları doğrudan uygulansın diye. Dezavantajı, SQL'in elle yazılmasıdır.

## Komutlar

```powershell
python manage.py migrate    # tabloları + indeksleri oluşturur (tekrar çalıştırmak güvenli)
python manage.py seed       # örnek veriyi yükler (önce tabloları boşaltır)
python manage.py sorgular   # örnek sorguları çalıştırır
python manage.py demo       # CRUD işlemlerini adım adım gösterir
pytest                      # tüm testler (Hafta 6 itibarıyla 61 test)
```

## Elle açıklanan ilişki ve kısıtlar

**1) kullanicilar – abonelikler (1-1):**
`abonelikler.kullanici_id` hem `REFERENCES kullanicilar(id)` hem de `UNIQUE`.
REFERENCES sayesinde var olmayan bir kullanıcıya abonelik açılamaz.
UNIQUE sayesinde bir kullanıcının ikinci aboneliği olamaz. İkisi birlikte 1-1 ilişki kurar.
`ON DELETE CASCADE`: kullanıcı silinince aboneliği de silinir.

**2) cikarim_kayitlari – sema_alanlari (N-N):** Doğrudan bağlanamaz. Bunun yerine
`cikarim_degerleri` ara tablosu iki yabancı anahtar taşır: `cikarim_id` ve `alan_id`.
`UNIQUE (cikarim_id, alan_id)` ile aynı çıkarımda aynı alan iki kez yazılamaz.

**3) CHECK chk_kalan_kredi:** `kalan_kredi BETWEEN 0 AND aylik_kredi`.
Kredi eksiye düşemez. Bu kural uygulama kodunda unutulsa bile veritabanı reddeder.

**4) ON DELETE RESTRICT (cikarim_kayitlari.sema_id):** Bir şemayla yapılmış çıkarım
varken şema silinemez. Böylece geçmiş kayıtlar anlamsız hale gelmez.

## İndeks kararları

| İndeks | Neden? |
|---|---|
| `belgeler (kullanici_id, yuklenme_tarihi DESC)` | "Kullanıcının belgeleri, en yeni önce" en sık sorgu |
| `cikarim_kayitlari (belge_id)` | Belgenin çıkarımları; CASCADE silmede hızlı arama |
| `cikarim_kayitlari (olusturma_tarihi) WHERE durum='bekliyor'` | Kısmi indeks: sadece bekleyen işler, küçük ve hızlı |
| `cikarim_kayitlari (sema_id)`, `cikarim_degerleri (alan_id)` | Yabancı anahtar; RESTRICT kontrolünde arama |

**Eklenmeyenler:** `email` ve abonelikteki `kullanici_id` (UNIQUE zaten indeks oluşturur),
`dosya_turu` (sadece 4 değer, düşük seçicilik; indeks fayda sağlamaz, yük getirir).

## KVKK

Örnek verilerin hepsi uydurmadır: `@ornek.test` e-postaları, "(Örnek)" ekli firma adları,
gerçek olmayan vergi numaraları ve "sahte-hash" şifreler. Gerçek kişisel veri yoktur.
Gerçek kullanıcıların yüklediği belgeler `uploads/` klasöründe tutulur; bu klasör
`.gitignore` ile Git'e gönderilmez.
