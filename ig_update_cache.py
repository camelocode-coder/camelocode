# -*- coding: utf-8 -*-
import os, sys, re, json, urllib.request, urllib.error

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(SCRIPT_DIR, "_ig_session")
CACHE_DIR    = os.path.join(SCRIPT_DIR, "_ig_cache")
META_FILE    = os.path.join(CACHE_DIR, "_meta.json")
IG_USERNAME  = os.environ.get("IG_USERNAME", "camelocode")
BOT_UA       = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
MAX_POSTS    = 18

print(); print("=" * 55); print("  Instagram Cache Updater"); print("=" * 55)

try:
    import instaloader
except ImportError:
    print("Brak instaloader: pip install instaloader"); sys.exit(1)

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Logowanie ─────────────────────────────────────────
if not os.path.exists(SESSION_FILE):
    print("Brak pliku sesji. Zaloguj sie.")
    username = input(f"  Uzytkownik [{IG_USERNAME}]: ").strip() or IG_USERNAME
    if "@" in username:
        username = username.split("@")[0]
    password = input("  Haslo: ")
    L = instaloader.Instaloader(quiet=True,
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False)
    try:
        L.login(username, password)
        L.save_session_to_file(SESSION_FILE)
        print("  Zalogowano!")
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        code = input("  Kod 2FA: ").strip()
        L.two_factor_login(code)
        L.save_session_to_file(SESSION_FILE)
    except Exception as e:
        print(f"  Blad: {e}"); sys.exit(1)
else:
    L = instaloader.Instaloader(quiet=True,
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False)
    try:
        L.load_session_from_file(IG_USERNAME, SESSION_FILE)
        print(f"Sesja zaladowana dla @{IG_USERNAME}")
    except Exception as e:
        print(f"Sesja wygasla: {e}")
        os.remove(SESSION_FILE); sys.exit(1)

# ── Pobierz posty ──────────────────────────────────────
print(f"\nPobieranie postow z @{IG_USERNAME}...")
shortcodes = []
try:
    # Proba 1: przez sesje
    profile = instaloader.Profile.from_username(L.context, IG_USERNAME)
    for post in profile.get_posts():
        if len(shortcodes) >= MAX_POSTS: break
        shortcodes.append(post.shortcode)
    print(f"Znaleziono {len(shortcodes)} postow (przez sesje).")
except Exception as e:
    print(f"Sesja nie dziala: {e}")
    print("Proba bez sesji (publiczny profil)...")
    try:
        L2 = instaloader.Instaloader(quiet=True,
            download_pictures=False, download_videos=False,
            download_video_thumbnails=False, download_geotags=False,
            download_comments=False, save_metadata=False)
        profile = instaloader.Profile.from_username(L2.context, IG_USERNAME)
        for post in profile.get_posts():
            if len(shortcodes) >= MAX_POSTS: break
            shortcodes.append(post.shortcode)
        print(f"Znaleziono {len(shortcodes)} postow (bez sesji).")
    except Exception as e2:
        print(f"Blad bez sesji: {e2}")
        # Proba 3: czytaj z istniejacego meta jesli jest
        if os.path.exists(META_FILE):
            with open(META_FILE) as f:
                old_meta = json.load(f)
            shortcodes = [m["shortcode"] for m in old_meta]
            print(f"Uzyto {len(shortcodes)} shortcodes z poprzedniego cache.")
        else:
            print("Brak shortcodes. Koniec."); sys.exit(1)

if not shortcodes:
    print("Brak postow."); sys.exit(0)

# ── Pobierz miniatury ─────────────────────────────────
p_img  = re.compile(r'property="og:image"\s+content="([^"]+)"')
p_img2 = re.compile(r'content="([^"]+)"\s+property="og:image"')
p_desc = re.compile(r'property="og:description"\s+content="([^"]+)"')
p_dsc2 = re.compile(r'content="([^"]+)"\s+property="og:description"')

meta = []; new_count = 0; cached_count = 0
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
        req = urllib.request.Request(link, headers={"User-Agent": BOT_UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="replace")
        m_i = p_img.search(html) or p_img2.search(html)
        m_d = p_desc.search(html) or p_dsc2.search(html)
        thumb   = m_i.group(1) if m_i else ""
        caption = m_d.group(1)[:120] if m_d else ""
        if thumb:
            req2 = urllib.request.Request(thumb, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://www.instagram.com/",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
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
    except Exception as e:
        print(f"blad: {e}")
        meta.append({"shortcode": sc, "caption": "", "link": link})

with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print()
print("=" * 55)
print(f"  Nowe:    {new_count}")
print(f"  Cache:   {cached_count}")
print(f"  Lacznie: {len(meta)}")
print("=" * 55)
