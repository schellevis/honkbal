# AGENTS.md

Werkhandleiding voor autonome agenten in deze repository. De inhoud is parallel aan `CLAUDE.md`. Normatief contract: `SPEC.md`.

## Project in één zin

Honkbal.net is een Python/uv static-site generator die MLB-wedstrijden in Nederlandse tijd rendert naar `docs/`; browser-side ES-modules verzorgen scores/standen live via de MLB Stats API, favorieten via `localStorage` en offline-gedrag via een service worker; CI bouwt en publiceert de statische output.

## Hoe het echt werkt

### Build-time pipeline

1. **Fetch** (`uv run honkbal fetch`): haalt de MLB-ticketingfeed op per team-ID (mapping in `honkbal/config/feeds.py`); schrijft gecachte JSON naar `.data/`. Na `season.windows.ps` ook ESPN-postseason-API.
2. **Parse**: `honkbal/parse/schedule.py` zet CSV om naar een lijst van getypte `Game`-objecten (NY→Amsterdam tijdzone-conversie; TBD-afhandeling; allowlist; dedup); `honkbal/parse/espn_postseason.py` levert `PostseasonData`.
3. **Render** (`uv run honkbal render`): `honkbal/render/pages.py` bouwt Jinja2-context via `render/context.py`, rendert alle pagina's naar `docs/` met autoescape aan. De eerste 250 wedstrijden staan inline in de HTML; de rest schrijft `render/tail.py` als HTML-fragmentblokken naar `<pagina>.tail.json` (SPEC §5.9). Daarna kopieert de CLI statische assets vanuit `frontend/` naar `docs/`.
4. **Config-validatie**: `honkbal/season.py` valideert het actieve seizoensblok (Pydantic + `@model_validator`). Een ongeldige datum of ontbrekend verplicht veld → `ConfigError` → de build faalt **luid vóór publicatie**.
5. **`version.txt`**: in CI geschreven door de workflow (`${GITHUB_SHA::12}-${GITHUB_RUN_NUMBER}`); bij lokale builds valt de CLI terug op de mtime van `style.css`. Niet handmatig committen.

### Browser-side runtime

- `frontend/js/scores.js`: live scores via MLB Stats API (5-daags venster), gecached per dag in `localStorage`, sortering favorieten boven.
- `frontend/js/standings.js`: standen via MLB Stats API met seizoenjaar dat server-side in de HTML is ingebakken.
- `frontend/js/loadmore.js`: haalt `<pagina>.tail.json` op (network-first) en plakt extra wedstrijdrijen aan de pagina.
- `frontend/js/favorites.js`: gedeelde module voor opslaan/lezen/highlighten favoriete teams.
- `frontend/js/settings.js`: beheert de favorieten-checkbox-grid.
- `frontend/js/sw.js`: service worker — HTML en CSS **network-first**, afbeeldingen/fonts **cache-first**; PRECACHE-lijst bevat alle schedule- en team-pagina's. **Bump de `CACHE`-naam** bij elke wijziging van PRECACHE-inhoud of caching-strategie.

### Injecteerbare klok

Alle domeinlogica neemt een `Clock`-argument (protocol in `honkbal/clock.py`). Gebruik nooit kale `datetime.now()` in domeincode. Tests pinnen de klok via `FrozenClock`.

## Sleutelbevelen

```bash
# Installatie
uv sync                          # deps installeren (uv.lock is gecommit)
npm ci                           # frontend-devdeps (Playwright)

# Python-tests + lint
uv run pytest -q                 # alle Python-tests
uv run ruff check .              # lint

# Frontend-tests
npm run test:unit                # node:test (sortering, cache, DOM-stubs)
npm run test:e2e                 # Playwright headless (DOM, offline, SW)
npm test                         # beide

# Bouwen
uv run honkbal fetch             # data ophalen -> .data/
uv run honkbal render            # renderen -> docs/ (op bestaande .data/)
uv run honkbal build             # fetch + render in één stap

# Vlaggen
uv run honkbal --now 2026-04-01T20:00:00+02:00 render   # reproduceerbare klok
uv run honkbal render --out docs --data-dir .data        # expliciet paden
HONKBAL_NO_FETCH=1 uv run honkbal fetch                  # fetch overslaan (bestaande cache houden)
```

## Repo-structuur

```
pyproject.toml                 # uv-project, deps (jinja2, httpx, pydantic), ruff + pytest config
honkbal/
  clock.py                     # Clock protocol, SystemClock, FrozenClock
  season.py                    # select_active_season, load_windows, ConfigError (Pydantic-validatie)
  models.py                    # Game, ScheduleMeta, PostseasonGame, PostseasonData, Enrichment
  config/
    seasons.py                 # RAW_SEASONS: seizoensblokken per jaar
    feeds.py                   # TEAM_FEEDS: team_id <-> team mapping (30 MLB-teams + all-star)
    teams.py                   # teams_nl, teams_al, slugs, abbreviations, allowlist
    toggles.py                 # SHOW_GAMES=250, LOAD_MORE_BATCH=250, ESPNCAP=3000 etc.
    calendar_nl.py             # Nederlandse dag- en maandnamen
  fetch/
    schedule.py                # MLB ticketing-CSV ophalen per team-feed
    espn_postseason.py         # ESPN-API ophalen -> cache in .data/
    discover_feeds.py          # Eenmalig diagnostisch: range 105..161 -> team_id-mapping
    http.py                    # httpx-client met throttle (geen retry; drempel + last-known-good vangt fouten)
  parse/
    schedule.py                # CSV -> list[Game] (tz, TBD, allowlist, dedup, sortering)
    espn_postseason.py         # ESPN-JSON -> PostseasonData
  render/
    pages.py                   # render_site: alle pagina's -> docs/
    context.py                 # bouwt Jinja2-templatecontext
    filters.py                 # tijdfilters per pagina (ochtend/avond/nacht/alles/team)
    labels.py                  # datumkoppen, postseason-fase-labels, countdown
    logos.py                   # team-slug, <picture>/dark-mode, all-star-mapping
    tail.py                    # rest-rijen -> <pagina>.tail.json
    env.py                     # Jinja2-omgeving (autoescape aan)
  templates/
    base.html  nav.html  schedule.html  scores.html  standings.html
    settings.html  debug.html  offline.html  _rows.html
  cli.py                       # argparse: honkbal fetch / render / build
  cli_fetch.py                 # cmd_fetch implementatie
  cli_version.py               # resolve_asset_version (version.txt of style.css mtime)
frontend/
  css/
    style.css                  # custom CSS
    bootstrap-grid.min.css     # grid-hulp
  js/
    favorites.js  scores.js  standings.js  settings.js  loadmore.js  sw.js
    util/  diamond.js  dom.js  logo.js  time.js
  static/
    favicon.ico  icon.png  manifest.json  404.html
    img/                       # team-logo's (PNG)
tests/
  conftest.py                  # FrozenClock-fixture
  fixtures/                    # vastgepinde CSV + ESPN-JSON-snapshots
  unit/                        # per module
  integration/                 # schone-checkout build
  golden/                      # DOM-fragment-snapshots
frontend/test/                 # node:test (favorites, scores, standings, loadmore, ...)
frontend/e2e/                  # Playwright (DOM, offline, SW)
.github/workflows/
  build.yml                    # volledige build + fetch + publicatie (cron + handmatig)
  rebuild.yml                  # render zonder fetch (handmatig, vereist data-cache)
  ci.yml                       # PR-gate: volledige suite (ruff + pytest + node:test + Playwright)
```

## CI/CD

### `build.yml` — volledig (cron + `workflow_dispatch`)

1. **gate-job** (lichte deploy-gate): `uv sync --frozen` → `ruff check` → `pytest -q`. Geen node:test/Playwright — die draaien op push/PR in `ci.yml`; een cron-deploy gebruikt dezelfde commit met alleen verse data, en de render-stap valideert config en faalt luid. Blokkeert de build-job.
2. **build-job**: data-cache herstellen → `honkbal fetch` → `version.txt` schrijven → `honkbal render` → data-cache opslaan → publicatie-artifact.

### `rebuild.yml` — geen fetch (handmatig)

Zelfde lichte gate-job. Build-job herstelt de data-cache (faalt luid als die ontbreekt) → `honkbal render` → publicatie-artifact. Bedoeld voor layout-/template-fixes zonder nieuwe data.

### `ci.yml` — volledige PR-gate

Draait op push naar `main` en bij pull requests: `uv sync --frozen` → `ruff check` → `pytest -q` → node:test → Playwright headless. Handhavingspunt voor frontend-regressies. Geen publicatie.

**`docs/` en `version.txt` worden door CI gegenereerd en staan in `.gitignore`. Nooit handmatig committen.**

## Publieke repo-hygiëne

Deze repository is publiek. Behandel alles in de tree — code, docs, workflows, tests, fixtures,
snapshots en agenthandleidingen — als openbaar materiaal.

Voorzorgsmaatregelen:

- Commit nooit secrets, tokens, accountconfig, lokale instellingen, privé-URL's, persoonlijke data
  of operationele infrastructuurdetails die niet nodig zijn om de code te begrijpen.
- Houd gegenereerde en lokale artefacten uit Git: `docs/`, `version.txt`, `.data/`,
  `.claude/settings.local.json`, `node_modules/`, `.venv/`, caches en test-output.
- Fixtures en snapshots mogen alleen publieke, minimale testdata bevatten. Strip headers,
  metadata en ruwe payloads die niet nodig zijn voor de test.
- Gebruik CI-secretbeheer voor echte waarden; documenteer configuratie met placeholders of
  generieke namen.
- Controleer vóór commit/publicatie minimaal `git status --short --ignored=matching`, gerichte
  `rg`/`git grep`-scans op secret- en opsec-termen, en bij imports of history-wijzigingen ook de
  te publiceren Git-history.

## Een nieuwe pagina of asset toevoegen

### Nieuwe HTML-pagina

1. Voeg een template toe aan `honkbal/templates/`.
2. Voeg de render-aanroep toe aan `render/pages.py` (en bijbehorende context in `render/context.py`).
3. Voeg de URL toe aan `PRECACHE` in `frontend/js/sw.js` als de pagina offline beschikbaar moet zijn.
4. **Bump de `CACHE`-naam** in `sw.js` zodat oude caches worden verlaten.

### Nieuw statisch bestand of asset

1. Zet het bestand in `frontend/css/`, `frontend/js/`, `frontend/static/` of `frontend/static/img/` — naargelang het type.
2. De CLI (`cli.py` → `_copy_static_assets`) kopieert het automatisch naar `docs/` bij de eerstvolgende render.
3. Let op: `frontend/js/sw.js` wordt naar `docs/sw.js` (root) gekopieerd; andere JS naar `docs/js/`.

## Jaarlijks onderhoud (verplicht)

Voeg elk nieuw seizoen toe in `honkbal/config/seasons.py`:

```python
2027: {
    "reg": "26-03-2027", "showfrom": "26-03-2027", "einde": "10-11-2027",
    "ps": "30-09-2027", "wc": "30-09-2027", "ds": "04-10-2027",
    "cs": "12-10-2027", "ws": "24-10-2027",
    "new": "01-01-2028", "hide": "01-02-2028",
    # "newreg": "...",    # bewust weglaten als 2028 opening day nog onbekend is
    # "allstargame": "...",
},
```

Verplichte velden: `reg`, `showfrom`, `einde`, `ps`, `wc`, `ds`, `cs`, `ws`, `new`, `hide`. Optioneel: `newreg`, `allstargame`, `uitzondering`.

`honkbal/season.py` valideert het blok bij elke build: ongeldige datumstring (bijv. `30-02-2027`), ontbrekend verplicht veld of geschonden invariant (bijv. `ps > einde`) → `ConfigError` → build mislukt.

Controleer daarna: default-tab op de frontpage, datumkoppen in `debug.html`, output van `docs/debug.html`.

## Hoe te testen (agenten-perspectief)

- Schrijf nooit netwerkaanroepen in tests; gebruik fixtures in `tests/fixtures/` en `frontend/test/fixtures/`.
- Pin de klok altijd via `FrozenClock` — nooit kale `datetime.now()` in domeincode of tests.
- Voeg tabel-gedreven cases toe voor uurgrenzen (02/03/04/06/07/13/14/22/23), TBD-wedstrijden en `show_games`-splitsing (250 inline / rest in tail.json).
- Golden-snapshots zitten in `tests/golden/` en `frontend/test/` — update die bewust, niet per ongeluk.
- Voer de volledige testsuite uit voor elke commit: `uv run pytest -q && npm test`.

## Bekende valkuilen

- **Kale `datetime.now()` in domeincode is verboden.** Gebruik altijd `clock.now()` — anders zijn tests niet deterministisch en is `--now` zinloos.
- **Config-validatie faalt de build hard.** Een seizoensblok met een typefout in een datum of een ontbrekend verplicht veld blokkeert render én publicatie. Dat is opzettelijk.
- **Service-worker cache-versie.** CSS en HTML worden **network-first** gehaald; toch moet de `CACHE`-naam in `sw.js` worden opgehoogd bij PRECACHE-wijzigingen, zodat verouderde pre-caches worden verwijderd.
- **`localStorage`-favorieten zijn browser-lokaal.** Testen in een andere browser of incognito geeft een andere uitkomst.
- **`localStorage`-score-cache is versiegebonden.** Bij wijzigingen in de datashape van `scores.js` de cacheversie in dat bestand ophogen, anders werken bestaande gebruikers met een incompatibele payload.
- **`config/feeds.py` (team-mapping + `ALLSTAR_FEED_ID`) is live gevalideerd op 2026-06-22** (30/30 teams + all-star, 0 mismatches). De feed-id's kunnen per seizoen veranderen; hervalideer met een live `discover_feeds`-run over range 105..161 bij twijfel of feed-wijzigingen.
- **`rebuild.yml` faalt luid** als er geen data-cache in Actions bestaat. Draai eerst `build.yml`.
- **`HONKBAL_NO_FETCH=1`** slaat fetch over en behoudt `.data/` ongewijzigd — handig bij lokale render-only iteraties.
- **`next_year` wordt legacy berekend** (vóór de rollover, SPEC §4.3) — bewuste eigenaarsbeslissing, geen bug.

## Wat je niet moet committen

- `docs/` (build-artifact, CI-verantwoordelijkheid)
- `version.txt` (CI-geschreven)
- `.data/` (fetch-cache; CI beheert via actions/cache)
- `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- `test-results/`, `playwright-report/`

## Referenties

- **SPEC.md** — normatief contract voor alle gedrag
