# v3.5 — AnimeWorld catalogs

New Stremio catalogs (the addon had none before):

| Catalog | Type | Source |
|---|---|---|
| RareToons · Recently Updated (genre: Anime / Cartoon) | series, movie | local index; shows whose episode count grew come first |
| AnimeWorld · Newest Drops | series | watchanimeworld home page |
| AnimeWorld · Most Watched | series, movie | watchanimeworld home page |
| AnimeWorld · Browse by Genre (+ search) | series, movie | `/category/genre/<slug>/` |

Streams for `awi:` ids: the AnimeWorld title is matched against the RareToons
index and played through the existing HLS pipeline. Titles RareToons does not
carry get one "open on site" link instead.

Env vars: `AWI_BASE`, `AWI_GENRES="Action,Comedy,Sci-Fi"`, `AWI_TTL_HOME`, `AWI_TTL_PAGE`.
Offline test: `python3 test_awi.py` (needs the stubbed curl_cffi shown in the file).
