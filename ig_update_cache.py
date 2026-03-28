# -*- coding: utf-8 -*-
"""
ig_update_cache.py

Uzycie lokalne (Twoj komputer):
    python ig_update_cache.py

Uzycie w GitHub Actions (automatyczne):
    Sesja jest odczytywana z IG_SESSION_B64 secret - nie trzeba nic robic recznie.
"""

import os
import sys
import re
import json
import urllib.request
import urllib.error

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(SCRIPT_DIR, "_ig_session")
CACHE_DIR    = os.path.join(SCRIPT_DIR, "_ig_cache")
META_FILE    = os.path.join(CACHE_DIR, "_meta.json")
IG_USERNAME  = os.environ.get("IG_USERNAME", "camelocode")
BOT_UA       = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
MAX_POSTS    = 18

print()
print("=" * 55)
print("  Instagram Cache Updater")
print("=" * 55)

try:
    import instaloader
except ImportError:
    print("Brak instaloader!")
    print("Zainstaluj: pip install instaloader")
    sys.exit(1)

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Logowanie (tylko jesli brak pliku sesji) ──────────────────────────
if not os.path.exists(SESSION_FILE):
    print()
    print("Brak pliku sesji. Musisz sie zalogowac.")
    print(f"WAZNE: podaj nazwe uzytkownika (np. camelocode), NIE email!")
    print()
    username = input(f"  Nazwa uzytkownika [{IG_USERNAME}]: ").strip() or IG_USERNAME
    if "@" in username:
        username = username.split("@")[0]
        print(f"  Zmieniono na: {username}")
    password = input("  Haslo (bedzie widoczne): ")
    if not password:
        print("Haslo nie moze byc puste!")
        sys.exit(1)
    print()
    print("  Logowanie...")
    L = instaloader.Instaloader(quiet=True,
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False)
    try:
        L.login(username, password)
        L.save_session_to_file(SESSION_FILE)
        print("  Zalogowano! Sesja zapisana.")
    except instaloader.exceptions.BadCredentialsException:
        print("  BLAD: Zle haslo lub nazwa uzytkownika.")
        sys.exit(1)
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        code = input("  Kod 2FA: ").strip()
        L.two_factor_login(code)
        L.save_session_to_file(SESSION_FILE)
        print("  Zalogowano z 2FA!")
    except instaloader.exceptions.ConnectionException as e:
        if "checkpoint" in str(e).lower() or "challenge" in str(e).lower():
            print("  Instagram wymaga weryfikacji!")
            print("  Zaloguj sie przez przegladarke na instagram.com i potwierdz logowanie.")
            print("  Potem uruchom ten skrypt ponownie.")
        else:
            print(f"  BLAD polaczenia: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  BLAD: {e}")
        sys.exit(1)
else:
    L = instaloader.Instaloader(quiet=True,
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False)
    try:
        L.load_session_from_file(IG_USERNAME, SESSION_FILE)
        print(f"Sesja zaladowana dla @{IG_USERNAME}")
    except Exception as e:
        print(f"Sesja wygasla lub uszkodzona: {e}")
        print("Usuwam stara sesje. Uruchom skrypt ponownie.")
        os.remove(SESSION_FILE)
        sys.exit(1)

# ── Pobierz liste postow ──────────────────────────────────────────────
print()
print(f"Pobieranie listy postow z @{IG_USERNAME}...")
try:
    profile    = instaloader.Profile.from_username(L.context, IG_USERNAME)
    shortcodes = []
    for post in profile.get_posts():
        if len(shortcodes) >= MAX_POSTS:
            break
        shortcodes.append(post.shortcode)
    print(f"Znaleziono {len(shortcodes)} postow.")
except instaloader.exceptions.ProfileNotExistsException:
    print(f"BLAD: Profil @{IG_USERNAME} nie istnieje lub jest prywatny.")
    sys.exit(1)
except Exception as e:
    print(f"BLAD pobierania profilu: {e}")
    if "login" in str(e).lower() or "401" in str(e) or "403" in str(e):
        print("Sesja wygasla. Usuwam plik sesji.")
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    sys.exit(1)

if not shortcodes:
    print("Brak postow do pobrania.")
    sys.exit(0)

# ── Pobierz miniatury przez og:image ─────────────────────────────────
p_img  = re.compile(r'property="og:image"\s+content="([^"]+)"')
p_img2 = re.compile(r'content="([^"]+)"\s+property="og:image"')
p_desc = re.compile(r'property="og:description"\s+content="([^"]+)"')
p_dsc2 = re.compile(r'content="([^"]+)"\s+property="og:description"')

meta         = []
new_count    = 0
cached_count = 0

print()
for i, sc in enumerate(shortcodes):
    cache_path = os.path.join(CACHE_DIR, f"{sc}.jpg")
    link       = f"https://www.instagram.com/p/{sc}/"

    if os.path.exists(cache_path):
        print(f"  [{i+1:2}/{len(shortcodes)}] {sc}  cache OK")
        meta.append({"shortcode": sc, "caption": "", "link": link})
        cached_count += 1
        continue

    print(f"  [{i+1:2}/{len(shortcodes)}] {sc}  pobieranie...", end=" ", flush=True)
    try:
        req = urllib.request.Request(link, headers={
            "User-Agent": BOT_UA, "Accept": "text/html,*/*"
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="replace")

        m_img  = p_img.search(html) or p_img2.search(html)
        m_desc = p_desc.search(html) or p_dsc2.search(html)
        thumb   = m_img.group(1)  if m_img  else ""
        caption = m_desc.group(1)[:120] if m_desc else ""

        if thumb:
            req2 = urllib.request.Request(thumb, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                "Referer":    "https://www.instagram.com/",
                "Accept":     "image/webp,image/apng,image/*,*/*;q=0.8",
            })
            with urllib.request.urlopen(req2, timeout=15) as r2:
                img_bytes = r2.read()
            with open(cache_path, "wb") as f:
                f.write(img_bytes)
            meta.append({"shortcode": sc, "caption": caption, "link": link})
            print(f"OK  ({len(img_bytes)//1024} KB)")
            new_count += 1
        else:
            print("brak og:image")
            meta.append({"shortcode": sc, "caption": "", "link": link})

    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        meta.append({"shortcode": sc, "caption": "", "link": link})
    except Exception as e:
        print(f"blad: {e}")
        meta.append({"shortcode": sc, "caption": "", "link": link})

# ── Zapisz meta ───────────────────────────────────────────────────────
with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print()
print("=" * 55)
print(f"  Gotowe!")
print(f"  Nowe posty:    {new_count}")
print(f"  Z cache:       {cached_count}")
print(f"  Lacznie:       {len(meta)}")
print(f"  Folder:        {CACHE_DIR}")
print("=" * 55)
