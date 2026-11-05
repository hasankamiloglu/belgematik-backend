"""
kimlik_no.py - Vergi kimlik no (VKN) ve TC kimlik no (TCKN) doğrulama.

Bu numaraların SON HANESİ, önceki hanelerden hesaplanan bir KONTROL HANESİDİR.
OCR bir rakamı yanlış okursa (ör. 8 yerine 3) hesap tutmaz ve hata yakalanır.
Sadece "10 hane mi?" diye bakmak bunu yakalayamaz.
"""


def vkn_gecerli_mi(vkn):
    """
    10 haneli Vergi Kimlik Numarası kontrolü (Gelir İdaresi algoritması).

    Adımlar (ilk 9 hane için, i = 0..8):
        1) a = (hane + 9 - i) mod 10
        2) b = (a * 2^(9 - i)) mod 9      ; a != 0 iken b = 0 çıkarsa b = 9 alınır
        3) b'ler toplanır
    Kontrol hanesi = (10 - toplam mod 10) mod 10  ->  10. haneye eşit olmalı.
    """
    if not (isinstance(vkn, str) and len(vkn) == 10 and vkn.isdigit()):
        return False
    toplam = 0
    for i in range(9):
        a = (int(vkn[i]) + 9 - i) % 10
        b = (a * 2 ** (9 - i)) % 9
        if a != 0 and b == 0:
            b = 9
        toplam += b
    return (10 - toplam % 10) % 10 == int(vkn[9])


def tckn_gecerli_mi(tckn):
    """
    11 haneli TC Kimlik Numarası kontrolü.
        - İlk hane 0 olamaz
        - 10. hane = ((1.+3.+5.+7.+9. haneler) * 7 - (2.+4.+6.+8. haneler)) mod 10
        - 11. hane = (ilk 10 hanenin toplamı) mod 10
    """
    if not (isinstance(tckn, str) and len(tckn) == 11 and tckn.isdigit()) or tckn[0] == "0":
        return False
    h = [int(c) for c in tckn]
    tekler = h[0] + h[2] + h[4] + h[6] + h[8]
    ciftler = h[1] + h[3] + h[5] + h[7]
    return (tekler * 7 - ciftler) % 10 == h[9] and sum(h[:10]) % 10 == h[10]


def vergi_no_gecerli_mi(numara):
    """Şirketler 10 haneli VKN, şahıs şirketleri 11 haneli TCKN kullanır."""
    numara = str(numara or "")
    return vkn_gecerli_mi(numara) if len(numara) == 10 else tckn_gecerli_mi(numara)
