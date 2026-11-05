# Hafta 8 – VİZE: Ara Sürüm, Entegrasyon ve Sözlü Hazırlık

**Geliştirilen modül:** Ara sürüm (v0.7.0)

## Yapılan teknik çalışmalar

- [x] **Uçtan uca entegrasyon:** tek test, tüm modülleri sırayla çalıştırıyor (`tests/test_uctan_uca.py`)
- [x] **Bilinen hataların giderilmesi:** 6 hata (`docs/ilerleme-raporu-vize.md` → bölüm 6)
- [x] **Ara sürüm etiketleme:** iki depo da `v0.7.0` (Git tag) · `CHANGELOG.md` · anlamsal sürümleme
- [x] **Kısa demo senaryosu:** `docs/ilerleme-raporu-vize.md` → bölüm 8
- [x] **Sürekli entegrasyon:** GitHub Actions her push'ta backend testlerini ve frontend derlemesini çalıştırıyor
- [x] Toplam **99 test**

## Teslim edilen çıktılar

| Çıktı | Konum |
|---|---|
| Çalışan ara sürüm (etiketli) | GitHub → Tags → `v0.7.0` (iki depo) |
| Güncel yapay zekâ kullanım günlüğü | `docs/ai-kullanim-gunlugu.md` |
| Kısa ilerleme raporu | `docs/ilerleme-raporu-vize.md` |
| Sürüm notları | `CHANGELOG.md` (iki depo) |

## Kontrol kriterleri

| Kriter | Kanıt |
|---|---|
| Ara sürüm çalışıyor | `v0.7.0` etiketi, Actions yeşil, demo |
| Modüller entegre | `test_kullanici_senaryosu_bastan_sona` (kayıt → yükleme → OCR → doğrulama → veritabanı → yönetici → çıkış) |
| Öğrenci tüm kodu açıklayabiliyor | Sözlü sınav; her dosyada Türkçe açıklama satırları |

## Kavramlar

| Kavram | Bu projede |
|---|---|
| **Entegrasyon** | Ayrı yazılan modüllerin birlikte çalışması. `cikarim_servisi.belge_isle` 5 modülü sırayla çağırıyor |
| **Sürümleme** | `MAJOR.MINOR.PATCH`. Her hafta yeni özellik → MINOR arttı (0.2 → 0.7); `0.x` = geliştirme aşaması |
| **Regresyon** | Yeni kodun eski bir özelliği bozması. Her push'ta 99 testin tamamı çalışarak yakalanıyor |

## Sık yapılan hatalara karşı

| Hata | Bu projede |
|---|---|
| Entegrasyonu son ana bırakmak | Her hafta bir önceki modüle bağlandı (H6 → H7 OCR); uçtan uca test her push'ta çalışıyor |
| Ara sürümü etiketlememek | `git tag -a v0.7.0` (iki depo) |
| Açıklanamayan AI kodu taşımak | Tüm kodda Türkçe açıklamalar; AI kullanımı günlükte dürüstçe kayıtlı |
