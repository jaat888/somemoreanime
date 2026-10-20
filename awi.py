# -*- coding: utf-8 -*-
"""AnimeWorld (watchanimeworld) catalog source for the addon.

Python port of the selectors used by MSMods-Pro/AnimeWorldIndia-Api, so the
addon can offer "Newest Drops", "Most Watched" and genre browsing without
running the Node API next to it.

Everything here is best-effort scraping: if the site changes its markup a
catalog simply comes back empty, it never breaks the addon.  beautifulsoup4
is imported lazily - without it the AnimeWorld catalogs are just empty.
"""
import os
import re
import threading
import time

BASE = os.environ.get("AWI_BASE", "https://watchanimeworld.net").rstrip("/")
TTL_HOME = int(os.environ.get("AWI_TTL_HOME", "600"))      # home / lists, s
TTL_PAGE = int(os.environ.get("AWI_TTL_PAGE", "1800"))     # details, s

# Genre slugs as used in /category/genre/<slug>/.  "sci-fi" is confirmed by
# the API's README; the rest are the usual ones - override without editing
# code:  AWI_GENRES="Action,Comedy,Sci-Fi"
_DEFAULT_GENRES = ("Action", "Adventure", "Comedy", "Drama", "Fantasy",
                   "Horror", "Mystery", "Romance", "Sci-Fi", "Slice of Life",
                   "Sports", "Supernatural")
GENRES = [g.strip() for g in os.environ.get("AWI_GENRES", "").split(",")
          if g.strip()] or list(_DEFAULT_GENRES)

# Set by addon.py: fetch(url, referer=None) -> html text ("" on failure).
fetch = None

_cache = {}
_lock = threading.Lock()
_page_size = {}            # list path -> items per page (for skip -> page)


def _soup(html):
    from bs4 import BeautifulSoup          # lazy: optional dependency
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:
        return BeautifulSoup(html or "", "html.parser")


def _cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    try:
        val = fn()
    except Exception:
        val = None
    if val:                                  # never cache failures / empties
        with _lock:
            if len(_cache) > 600:
                _cache.pop(next(iter(_cache)))
            _cache[key] = (now, val)
        return val
    with _lock:                              # serve stale rather than nothing
        hit = _cache.get(key)
    return hit[1] if hit else val


def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def _img(el):
    if not el:
        return ""
    u = (el.get("src") or el.get("data-src") or "").strip()
    if u.startswith("//"):
        u = "https:" + u
    return u.replace("img.anime-world.co", "img.watchanimeworld.in")


def _slug_type(href):
    path = (href or "").split("?")[0].rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    typ = "series" if "/series/" in path else \
          "movie" if ("/movies/" in path or "/movie/" in path) else ""
    return slug, typ


def _card(node):
    a = node.select_one("a.lnk-blk") or node.select_one("a[href]")
    title = _text(node.select_one(".entry-title"))
    slug, typ = _slug_type(a.get("href") if a else "")
    if not (slug and title and typ):
        return None
    return {"slug": slug, "type": typ, "title": title,
            "poster": _img(node.select_one("img")),
            "season": _text(node.select_one(".post-ql")),
            "eps": _text(node.select_one(".year"))}


def parse_cards(html, selector=".post-lst > li"):
    out, seen = [], set()
    for n in _soup(html).select(selector):
        c = _card(n)
        if c and (c["type"], c["slug"]) not in seen:
            seen.add((c["type"], c["slug"]))
            out.append(c)
    return out


# ------------------------------------------------------------------ home --
def parse_home(html):
    s = _soup(html)
    data = {"newest": [], "popular_series": [], "popular_movies": []}
    for n in s.select("#widget_list_episodes-5 .swiper-slide, "
                      ".widget_list_episodes .swiper-slide"):
        c = _card(n)
        if c and all(c["slug"] != x["slug"] for x in data["newest"]):
            data["newest"].append(c)
    for key, sel in (("popular_series", "#torofilm_wdgt_popular-3 .top-picks__item"),
                     ("popular_movies", "#torofilm_wdgt_popular-4 .top-picks__item")):
        for n in s.select(sel)[:10]:
            a = n.select_one("a.item__card") or n.select_one("a[href]")
            im = n.select_one("img")
            slug, typ = _slug_type(a.get("href") if a else "")
            title = re.sub(r"^Image\s+", "", (im.get("alt") if im else "") or "")
            if slug and title:
                data[key].append({"slug": slug, "type": typ or
                                  ("movie" if key.endswith("movies") else "series"),
                                  "title": title, "poster": _img(im)})
    return data


def home():
    def run():
        html = fetch(BASE + "/") if fetch else ""
        d = parse_home(html) if html else None
        return d if d and any(d.values()) else None
    return _cached("home", TTL_HOME, run) or {}


# ---------------------------------------------------------------- browse --
def _list_url(path, page):
    return f"{BASE}/{path.strip('/')}/" + (f"page/{page}/" if page > 1 else "")


def browse(kind, genre=None, skip=0):
    """kind: 'series' | 'movie'.  One page of cards for Stremio's skip."""
    if genre:
        slug = re.sub(r"[^a-z0-9]+", "-", genre.lower()).strip("-")
        paths = [f"category/genre/{slug}"]
    else:
        paths = ["series" if kind == "series" else "movies"]
    path = paths[0]
    size = _page_size.get(path) or 20
    page = skip // size + 1

    def run():
        html = fetch(_list_url(path, page)) if fetch else ""
        items = parse_cards(html) if html else []
        if items and page == 1:
            _page_size[path] = len(items)
        return items or None
    items = _cached(f"b:{path}:{page}", TTL_HOME, run) or []
    # a genre page mixes series and movies - keep what the catalog asks for
    return [c for c in items if c["type"] == kind]


def search(query, kind):
    q = re.sub(r"\s+", "+", query.strip())

    def run():
        html = fetch(f"{BASE}/?s={q}") if fetch else ""
        return parse_cards(html, ".post-lst li") or None
    return [c for c in (_cached(f"s:{q}", TTL_HOME, run) or [])
            if c["type"] == kind]


# --------------------------------------------------------------- details --
def _parse_episodes(html):
    out = []
    for li in _soup(html).select("li"):
        num = _text(li.select_one(".num-epi"))
        m = re.search(r"(\d+)\s*[xX]\s*(\d+)", num) or \
            re.search(r"[sS](\d+)[eE](\d+)", num)
        title = _text(li.select_one(".entry-title"))
        if m and title:
            out.append({"season": int(m.group(1)), "episode": int(m.group(2)),
                        "title": title,
                        "thumb": _img(li.select_one("img"))})
    return out


def parse_details(html):
    s = _soup(html)
    body = " ".join(s.body.get("class", [])) if s.body else ""
    pid = re.search(r"postid-(\d+)", body)
    seasons = []
    for a in s.select("a[data-season]"):
        try:
            n = int(a.get("data-season"))
        except (TypeError, ValueError):
            continue
        if n not in seasons:
            seasons.append(n)
    bg = s.select_one(".bghd img.TPostBg") or s.select_one(".bgft img.TPostBg")
    bgu = (bg.get("src") or "") if bg else ""
    return {
        "title": _text(s.select_one("h1.entry-title")),
        "poster": _img(s.select_one("article.post.single img")),
        "background": ("https:" + bgu) if bgu.startswith("//") else bgu,
        "description": _text(s.select_one(".description")),
        "genres": [_text(a) for a in s.select(".genres a") if _text(a)],
        "languages": [_text(a) for a in s.select(".loadactor a") if _text(a)],
        "year": _text(s.select_one(".year .overviewCss")),
        "post_id": pid.group(1) if pid else "",
        "seasons": sorted(seasons),
        "episodes": _parse_episodes(str(s.select_one("#episode_by_temp") or "")),
    }


def details(kind, slug):
    folder = "series" if kind == "series" else "movies"

    def run():
        html = fetch(f"{BASE}/{folder}/{slug}/") if fetch else ""
        d = parse_details(html) if html else None
        return d if d and d.get("title") else None
    return _cached(f"d:{folder}:{slug}", TTL_PAGE, run)


def season_episodes(slug, post_id, season):
    def run():
        if not (fetch and post_id):
            return None
        url = (f"{BASE}/wp-admin/admin-ajax.php?action=action_select_season"
               f"&season={season}&post={post_id}")
        return _parse_episodes(fetch(url, referer=f"{BASE}/series/{slug}/")) or None
    return _cached(f"se:{slug}:{season}", TTL_PAGE, run) or []


def page_url(kind, slug):
    return f"{BASE}/{'series' if kind == 'series' else 'movies'}/{slug}/"
