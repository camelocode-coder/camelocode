# -*- coding: utf-8 -*-
"""
ig_update_cache.py

Dodawanie nowych postow:
  - Wpisz shortcode posta w liscie SHORTCODES ponizej
  - Shortcode to czesc URL: instagram.com/p/SHORTCODE/
  - Skrypt pobierze miniature automatycznie

Uruchomienie: python ig_update_cache.py
"""

import os, sys, re, json, subprocess, urllib.request, urllib.error, time

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR   = os.path.join(SCRIPT_DIR, "_ig_cache")
META_FILE   = os.path.join(CACHE_DIR, "_meta.json")
BOT_UA      = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
AUTO_PUSH   = True

# ── DODAJ TUTAJ SHORTCODES SWOICH POSTOW ─────────────
# Shortcode = czesc URL posta, np.:
# https://www.instagram.com/p/DWbTgplDaWv/
#                               ^^^^^^^^^^^
SHORTCODES = [
    "DWbTgplDaWv",
    # dodaj kolejne ponizej:
    # "ABC123xyz",
    # "DEF456uvw",
]
# ─────────────────────────────────────────────────────

print(); print("=" * 50)
print("  Instagram Cache Updater"); print("=" * 50)

os.makedirs(CACHE_DIR, exist_ok=True)

if not SHORTCODES:
    print("Brak shortcodes w liscie SHORTCODES!")
    print("Dodaj shortcodes postow do pliku ig_update_cache.py")
    sys.exit(1)

print(f"\n{len(SHORTCODES)} postow na liscie.")

# ── Pobierz miniatury ─────────────────────────────────
p_img  = re.compile(r'property="og:image"\s+content="([^"]+)"')
p_img2 = re.compile(r'content="([^"]+)"\s+property="og:image"')
p_desc = re.compile(r'property="og:description"\s+content="([^"]+)"')
p_dsc2 = re.compile(r'content="([^"]+)"\s+property="og:description"')

meta = []; new_count = 0; cached_count = 0
print()

for i, sc in enumerate(SHORTCODES):
    cache_path = os.path.join(CACHE_DIR, f"{sc}.jpg")
    link       = f"https://www.instagram.com/p/{sc}/"

    if os.path.exists(cache_path):
        print(f"  [{i+1:2}/{len(SHORTCODES)}] {sc}  cache OK")
        old_cap = ""
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE) as mf:
                    old = json.load(mf)
                old_cap = next((m.get("caption","") for m in old if m.get("shortcode")==sc), "")
            except Exception:
                pass
        meta.append({"shortcode": sc, "caption": old_cap, "link": link})
        cached_count += 1
        continue

    print(f"  [{i+1:2}/{len(SHORTCODES)}] {sc}  pobieranie...", end=" ", flush=True)
    try:
        req = urllib.request.Request(link, headers={
            "User-Agent": BOT_UA, "Accept": "text/html,*/*"
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="replace")

        m_i = p_img.search(html) or p_img2.search(html)
        m_d = p_desc.search(html) or p_dsc2.search(html)
        thumb   = m_i.group(1) if m_i else ""
        caption = m_d.group(1)[:120] if m_d else ""

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

        time.sleep(1)

    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        meta.append({"shortcode": sc, "caption": "", "link": link})
    except Exception as e:
        print(f"blad: {e}")
        meta.append({"shortcode": sc, "caption": "", "link": link})

# ── Usuń stare JPG ────────────────────────────────────
current = {m["shortcode"] for m in meta}
removed = 0
for fname in os.listdir(CACHE_DIR):
    if fname.endswith(".jpg") and fname[:-4] not in current:
        os.remove(os.path.join(CACHE_DIR, fname))
        print(f"  Usunieto: {fname}")
        removed += 1

with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print()
print("=" * 50)
print(f"  Nowe:     {new_count}")
print(f"  Cache:    {cached_count}")
print(f"  Usuniete: {removed}")
print(f"  Lacznie:  {len(meta)}")
print("=" * 50)

# ── Push do GitHub ────────────────────────────────────
if AUTO_PUSH and new_count > 0:
    print("\nPushowanie do GitHub...")
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"],
                      capture_output=True, check=True, cwd=SCRIPT_DIR)
        subprocess.run(["git", "add", "_ig_cache/"],
                      check=True, cwd=SCRIPT_DIR)
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=SCRIPT_DIR)
        if r.returncode != 0:
            subprocess.run(["git", "commit", "-m",
                f"chore: update cache ({new_count} nowych)"],
                check=True, cwd=SCRIPT_DIR)
            subprocess.run(["git", "push"], check=True, cwd=SCRIPT_DIR)
            print("Wypchnięto do GitHub!")
        else:
            print("Brak zmian.")
    except Exception as e:
        print(f"Git blad: {e}")
else:
    print("\nBrak nowych postow.")
