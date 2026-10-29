"""
test_on_isleme.py - Görsel doğrulama, kalite ölçümü ve ön işleme testleri.
Veritabanı GEREKMEZ.
"""

import io

import pytest
from PIL import Image

from app.services.preprocessing import goruntu
from app.services.preprocessing.goruntu import GorselHatasi
from tests.ornek_gorsel import bayt, fis


# ------------------------------------------------------------- doğrulama
def test_normal_fis_kabul_edilir_ve_puan_yuksek():
    sonuc = goruntu.isle(bayt(fis()), "jpg")
    assert sonuc["kalite_puani"] == 100
    assert sonuc["uyarilar"] == []
    assert (sonuc["genislik"], sonuc["yukseklik"]) == (800, 1200)


def test_bozuk_dosya_reddedilir():
    with pytest.raises(GorselHatasi, match="bozuk"):
        goruntu.isle(b"bu bir resim degil", "jpg")


def test_sahte_uzanti_reddedilir():
    """İçi PNG olan dosyaya .jpg adı verilmişse reddedilmeli (içeriğe güveniyoruz)."""
    with pytest.raises(GorselHatasi, match="uyuşmuyor"):
        goruntu.isle(bayt(fis(), "PNG"), "jpg")


def test_dusuk_cozunurluk_reddedilir():
    with pytest.raises(GorselHatasi, match="Çözünürlük"):
        goruntu.isle(bayt(fis(300, 500)), "jpg")


# ------------------------------------------------------- düşük kalite
def test_hafif_bulanik_uyariyla_kabul():
    sonuc = goruntu.isle(bayt(fis(bozulma="bulanik")), "jpg")
    assert sonuc["kalite_puani"] < 100
    assert any("bulanık" in u for u in sonuc["uyarilar"])


def test_cok_bulanik_reddedilir():
    with pytest.raises(GorselHatasi, match="düşük kaliteli"):
        goruntu.isle(bayt(fis(bozulma="cok_bulanik")), "jpg")


def test_karanlik_gorsel_uyari_verir():
    puan, uyarilar, _ = goruntu.kalite_olc(fis(bozulma="karanlik"))
    assert any("karanlık" in u for u in uyarilar)
    assert puan < 100


def test_soluk_gorsel_uyari_verir_ve_kontrast_artirilir():
    soluk = fis(bozulma="soluk")
    _, uyarilar, once = goruntu.kalite_olc(soluk)
    assert any("Kontrast" in u for u in uyarilar)
    _, _, sonra = goruntu.kalite_olc(goruntu.on_isle(soluk))
    assert sonra["kontrast"] > once["kontrast"]  # ön işleme kontrastı açtı


# --------------------------------------------------------- ön işleme
def test_on_isleme_gri_ve_kucultulmus():
    islenmis = goruntu.on_isle(fis(3000, 4000))
    assert islenmis.mode == "L"                   # gri tonlama
    assert max(islenmis.size) == goruntu.EN_BUYUK_KENAR  # 4000 -> 2000


def test_exif_yonu_duzeltilir():
    """Telefon 'yan çekildi' bilgisini EXIF'e yazar; görsel gerçekten döndürülmeli."""
    gorsel = fis(800, 1200)
    exif = Image.Exif()
    exif[0x0112] = 6  # 0x0112 = Orientation etiketi, 6 = 90 derece döndür
    tampon = io.BytesIO()
    gorsel.save(tampon, format="JPEG", exif=exif)
    acilan = goruntu.gorsel_ac(tampon.getvalue(), "jpg")
    assert acilan.size == (1200, 800)  # en ve boy yer değiştirdi
