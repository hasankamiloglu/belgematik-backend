"""
auth paketi - Kimlik doğrulama ve yetkilendirme (İŞ katmanı, Hafta 5).

    parola.py         -> Parolayı hash'leme (tuz + PBKDF2) ve doğrulama
    token.py          -> JWT token üretme ve çözme (oturum yönetimi)
    kimlik_servisi.py -> Kayıt, giriş, hesap kilitleme, çıkış akışı

Kimlik doğrulama (authentication) -> "Sen kimsin?"     (e-posta + parola)
Yetkilendirme   (authorization)  -> "Buna iznin var mı?" (kullanici / yonetici)
"""
