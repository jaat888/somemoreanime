#!/usr/bin/env python3
"""
Ek baar chalao — sab shows ka Cinemeta se description/genres fetch karke
meta_cache.json mein save kar do. Addon yeh file startup pe load karega.
"""
import json, re, time, sys
from urllib.parse import quote_plus
import urllib.request

CINEMETA = "https://v3-cinemeta.strem.io/catalog/{typ}/top/search={q}.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def _base_title(name):
    n = name
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"\s*[-–]?\s*(hindi|tamil|telugu|malayalam|bengali|multi|"
               r"dubbed|subbed|dub|sub|uncut|crunchyroll|jio\s*cinema)\b.*$",
               "", n, flags=re.I)
    n = re.sub(r"\bseason\s*\d+\b", " ", n, flags=re.I)
    n = re.sub(r"\bepisodes?\b", " ", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" -–")

def _slug_is_movie(name):
    s = name.lower()
    return "movie" in s and "episodes" not in s

def fetch_meta(title, is_movie):
    typ = "movie" if is_movie else "series"
    url = CINEMETA.format(typ=typ, q=quote_plus(title))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                    "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        metas = data.get("metas") or []
        if metas:
            m = metas[0]
            return {
                "description": m.get("description") or "",
                "genres": m.get("genres") or [],
                "imdb_id": m.get("imdbRating") and m.get("id") or "",
                "poster": m.get("poster") or "",
            }
    except Exception as e:
        pass
    return {}

# Load posters.json
with open("posters.json") as f:
    posters = json.load(f)

# Unique clean titles
seen, items = set(), []
for show_name in posters:
    clean = _base_title(show_name)
    if clean not in seen:
        seen.add(clean)
        items.append((clean, _slug_is_movie(show_name), show_name))

print(f"Total unique titles: {len(items)}")

# Load existing cache if any
try:
    with open("meta_cache.json") as f:
        cache = json.load(f)
    print(f"Existing cache: {len(cache)} entries")
except:
    cache = {}

# Fetch missing ones
done = 0
for clean_title, is_movie, orig in items:
    if clean_title in cache:
        continue
    result = fetch_meta(clean_title, is_movie)
    cache[clean_title] = result
    done += 1
    if done % 10 == 0:
        print(f"  {done} fetched... ({clean_title})")
        with open("meta_cache.json", "w") as f:
            json.dump(cache, f, indent=2)
    time.sleep(0.3)  # rate limit se bachne ke liye

with open("meta_cache.json", "w") as f:
    json.dump(cache, f, indent=2)

filled = sum(1 for v in cache.values() if v.get("description"))
print(f"\nDone! {len(cache)} total, {filled} with description")
