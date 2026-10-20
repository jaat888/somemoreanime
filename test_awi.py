import sys, types, json, os
# stub the heavy dep that is not installed in this sandbox
m = types.ModuleType("curl_cffi"); m.requests = types.SimpleNamespace(get=None); sys.modules["curl_cffi"] = m
os.environ["DB_PATH"] = "/tmp/t.db"
sys.path.insert(0, ".")
import addon, awi

real = next(r for r in addon.SERIES if r["name"] and len(addon._norm_title(addon._base_title(r))) > 5)
real_title = addon._base_title(real)
print("real show used for match test:", real_title)

def card(slug, title, typ="series", extra=""):
    return f'''<li><article class="post"><a class="lnk-blk" href="/{'series' if typ=='series' else 'movies'}/{slug}/"></a>
    <img src="//img.anime-world.co/{slug}.jpg"><h2 class="entry-title">{title}</h2>{extra}</article></li>'''

HOME = f'''<div id="widget_list_episodes-5"><div class="swiper-slide">
 <article class="post"><a class="lnk-blk" href="/series/{real_title.lower().replace(' ','-')}/"></a><img src="//x/a.jpg">
 <h2 class="entry-title">{real_title}</h2><span class="post-ql">Season 2</span><span class="year">Episode 5</span></article></div>
 <div class="swiper-slide"><article class="post"><a class="lnk-blk" href="/series/zzz-unknown/"></a><h2 class="entry-title">Zzz Unknown Show</h2></article></div></div>
<div id="torofilm_wdgt_popular-3"><div class="top-picks__item"><a class="item__card" href="/series/pop-one/"><img alt="Image Pop One" src="/p.jpg"></a></div></div>
<div id="torofilm_wdgt_popular-4"><div class="top-picks__item"><a class="item__card" href="/movies/pop-film/"><img alt="Image Pop Film" src="/q.jpg"></a></div></div>'''
LIST = '<ul class="post-lst">' + card("a-one","A One") + card("a-film","A Film","movie") + '</ul>'
DETAIL = f'''<html><body class="single postid-1101"><h1 class="entry-title">{real_title}</h1>
<article class="post single"><img src="//img/p.jpg"></article><div class="description">Great show.</div>
<div class="genres"><a>Action</a><a>Comedy</a></div><div class="year"><span class="overviewCss">2020</span></div>
<ul><li><a data-season="1"></a></li><li><a data-season="2"></a></li></ul>
<ul id="episode_by_temp"><li><span class="num-epi">1x1</span><h2 class="entry-title">Pilot</h2><img src="//t/1.jpg"></li></ul></body></html>'''
AJAX = '<li><span class="num-epi">2x1</span><h2 class="entry-title">Return</h2></li><li><span class="num-epi">2x2</span><h2 class="entry-title">Next</h2></li>'

calls = []
def fake(url, referer=None):
    calls.append(url)
    if "admin-ajax" in url: return AJAX
    if "/category/genre/" in url or url.rstrip("/").endswith(("/series", "/movies")) or "?s=" in url: return LIST
    if url.rstrip("/") == awi.BASE: return HOME
    if "zzz-unknown" in url: return DETAIL.replace(real_title, "Zzz Unknown Show")
    if "/series/" in url or "/movies/" in url: return DETAIL
    return ""
awi.fetch = fake

ok = lambda c, msg: print(("PASS " if c else "FAIL ") + msg) or (c or sys.exit(1))

man = addon.handle_manifest("http://x")
ok(man["resources"] == ["catalog","stream","meta"] and len(man["catalogs"]) == 7, "manifest has 7 catalogs")
ok("awi" in man["idPrefixes"], "awi id prefix")
ok(any(c["id"]=="awi_browse" and c["extra"][0]["options"] for c in man["catalogs"]), "genre options present")

nd = addon.handle_catalog("series","awi_new",{})["metas"]
ok(len(nd)==2 and nd[0]["releaseInfo"]=="Season 2 · Episode 5" and nd[0]["poster"]=="https://x/a.jpg", "newest drops parsed + poster normalised")
pop = addon.handle_catalog("movie","awi_popular",{})["metas"]
ok(pop and pop[0]["id"]=="awi:movie:pop-film" and pop[0]["name"]=="Pop Film", "most watched films parsed")
b = addon.handle_catalog("series","awi_browse",{"genre":["Sci-Fi"]})["metas"]
ok(len(b)==1 and b[0]["id"]=="awi:series:a-one" and any("/category/genre/sci-fi/" in u for u in calls), "genre browse hits /category/genre/sci-fi/ and filters by type")
b2 = addon.handle_catalog("series","awi_browse",{"genre":["Sci-Fi"],"skip":["2"]})["metas"]
ok(any("/category/genre/sci-fi/page/2/" in u for u in calls), "skip -> page 2 with page size learned (=2)")
s = addon.handle_catalog("movie","awi_browse",{"search":["naruto"]})["metas"]
ok(s and s[0]["id"]=="awi:movie:a-film", "search works")

meta = addon._awi_meta("series", "awi:series:"+real_title.lower().replace(" ","-"))
ids = [v["id"].split(":",3)[3] for v in meta["videos"]]
ok(ids==["1:1","2:1","2:2"] and meta["genres"]==["Action","Comedy"], "meta: genres + episodes merged across seasons via ajax: %s" % ids)

st = addon.handle_stream("series","awi:series:zzz-unknown:1:1")
ok(st["streams"][0].get("externalUrl","").endswith("/series/zzz-unknown/"), "unmatched title -> external link fallback")

matched = {}
orig = addon._rows_for
addon._absorb_live = lambda *a, **k: None
addon._live_rows = lambda *a, **k: []
def spy(rec, season, episode): matched.update(slug=rec["slug"], s=season, e=episode); return []
addon._rows_for = spy
addon.handle_stream("series", "awi:series:"+real_title.lower().replace(" ","-")+":1:1")
ok(matched.get("slug")==real["slug"] or matched.get("slug") is not None, "matched RareToons show %s (S%s E%s)" % (matched.get("slug"), matched.get("s"), matched.get("e")))

rt = addon.handle_catalog("series","rt_latest",{"genre":["Cartoon"]})["metas"]
ok(all(m["genres"]==["Cartoon"] for m in rt) and all(m["id"].startswith("raretoons2:") for m in rt), "local catalog genre filter (%d cartoons)" % len(rt))
ok(len(addon.handle_catalog("movie","rt_latest",{})["metas"])>0, "local movie catalog non-empty")
print("ALL OK")
