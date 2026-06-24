# CLAUDE.md

Werkhandleiding voor autonome agenten in deze repository. Normatief contract: `SPEC.md`.

## Project in één zin

Honkbal.net is een Python/uv static-site generator die MLB-wedstrijden in Nederlandse tijd rendert naar `docs/`; browser-side ES-modules verzorgen scores/standen live via de MLB Stats API, favorieten via `localStorage` en offline-gedrag via een service worker; CI bouwt en publiceert de statische output.

## Hoe het echt werkt

### Build-time pipeline

1. **Fetch** (`uv run honkbal fetch`): haalt de MLB-ticketingfeed op per team-ID (mapping in `honkbal/config/feeds.py`); schrijft gecachte JSON naar `.data/`. Vóór `season.windows.ps` ook MLB-StatsAPI-standen (`fetch/standings.py` → `.data/standings.json`, voor enrichment, faalt zacht). Na `season.windows.ps` ook ESPN-postseason-API.
2. **Parse**: `honkbal/parse/schedule.py` zet CSV om naar een lijst van getypte `Game`-objecten (NY→Amsterdam tijdzone-conversie; TBD-afhandeling; allowlist; dedup); `honkbal/parse/espn_postseason.py` levert `PostseasonData`.
3. **Enrich** (alleen reguliere seizoen): `honkbal/enrichment.py::enrich_games` kent elke wedstrijd een regelgebaseerde interessantheidsscore toe (`Enrichment{score,label,reasons}`) op basis van rivalry (`config/rivalries.py`), divisie/league (`config/teams.py`), standen (`.data/standings.json`) en optionele playoff-odds (`.data/playoff_odds.json`). Postseason wordt overgeslagen (`clock.now() >= season.windows.ps`). Zie SPEC §11.
4. **Render** (`uv run honkbal render`): `honkbal/render/pages.py` bouwt Jinja2-context via `render/context.py`, rendert alle pagina's naar `docs/` met autoescape aan. De eerste 250 wedstrijden staan inline in de HTML; de rest schrijft `render/tail.py` als HTML-fragmentblokken naar `<pagina>.tail.json` (SPEC §5.9). Daarna kopieert de CLI statische assets vanuit `frontend/` naar `docs/`. `cmd_render` draait stap 3 (enrich) vlak vóór het bouwen van de context; `enrichment_*` zit op `RowContext` maar wordt **nog niet getoond** in templates.
5. **Config-validatie**: `honkbal/season.py` valideert het actieve seizoensblok (Pydantic + `@model_validator`). Een ongeldige datum of ontbrekend verplicht veld → `ConfigError` → de build faalt **luid vóór publicatie**.
6. **`version.txt`**: in CI geschreven door de workflow (`${GITHUB_SHA::12}-${GITHUB_RUN_NUMBER}`); bij lokale builds valt de CLI terug op de mtime van `style.css`. Niet handmatig committen.

### Browser-side runtime

Logica-modules (geïmporteerd; exporteren `init`/functies, doen zelf geen self-init):

- `frontend/js/scores.js`: live scores via MLB Stats API (5-daags venster), gecached per dag in `localStorage`, sortering favorieten boven.
- `frontend/js/standings.js`: standen via MLB Stats API met seizoenjaar dat server-side in de HTML is ingebakken.
- `frontend/js/loadmore.js`: haalt `<pagina>.tail.json` op (network-first) en plakt extra wedstrijdrijen aan de pagina.
- `frontend/js/favorites.js`: gedeelde module voor opslaan/lezen/highlighten favoriete teams.
- `frontend/js/settings.js`: beheert de favorieten-checkbox-grid.
- `frontend/js/nav.js`: navigeert naar `<team>.html` bij wijziging van de team-`<select>` in de nav.

Entry-modules (extern geladen via `<script type="module">`, **geen inline blob** — SPEC §6.1; self-init op `DOMContentLoaded`):

- `scores-entry.js`, `standings-entry.js`, `settings-entry.js`: importeren `init` uit de bijbehorende logica-module en starten die op.
- `favorites-init.js`: past favoriet-highlights toe en luistert op cross-tab `storage`-events.
- `register-sw.js`: registreert `/sw.js` (scope `/`, `updateViaCache: "none"`) — vervangt de oude inline registratie (SPEC §6.5).

Service worker:

- `frontend/js/sw.js`: HTML en CSS **network-first**, afbeeldingen/fonts **cache-first**; PRECACHE-lijst bevat alle schedule- en team-pagina's. **Bump de `CACHE`-naam** bij elke wijziging van PRECACHE-inhoud of caching-strategie.

#### Versioned module-root (cachebusting voor ES-modules)

JS wordt bij render twee keer gekopieerd: naar `docs/js/` én naar `docs/js/v/<asset_version>/` (`cli.py` → `_copy_static_assets`). Templates verwijzen naar de versioned variant via `js_root = /js/v/<asset_version>` (geïnjecteerd in `render/pages.py`). Nieuwe build = nieuwe `asset_version` = nieuwe module-URL, dus de hele ES-modulegraph wordt vers opgehaald zonder dat de browser oude modules uit de HTTP-cache hergebruikt. `sw.js` is de uitzondering: die staat altijd op de root (`/sw.js`, scope `/`), niet versioned.

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
uv run honkbal build             # fetch + render in een stap

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
  enrichment.py                # enrich_games/score_game: regelgebaseerde interessantheid (SPEC §11)
  config/
    seasons.py                 # RAW_SEASONS: seizoensblokken per jaar
    feeds.py                   # TEAM_FEEDS: team_id <-> team mapping (30 MLB-teams + all-star)
    teams.py                   # teams_nl, teams_al, slugs, abbreviations, allowlist, TEAM_DIVISIONS/division_of
    rivalries.py               # handmatige rivalry-tiers (1..3) per teampaar (jaarlijks onderhoud)
    toggles.py                 # SHOW_GAMES=250, LOAD_MORE_BATCH=250, ESPNCAP=3000 etc.
    calendar_nl.py             # Nederlandse dag- en maandnamen
  fetch/
    schedule.py                # MLB ticketing-CSV ophalen per team-feed
    standings.py               # MLB-StatsAPI-standen -> .data/standings.json (enrichment-signaal)
    playoff_odds.py            # genormaliseerde playoff-odds lezen uit .data/playoff_odds.json (bron-adapter: zie SPEC §11.4)
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
    favorites.js  scores.js  standings.js  settings.js  loadmore.js  nav.js  sw.js
    favorites-init.js  scores-entry.js  standings-entry.js  settings-entry.js  # entry-modules (self-init)
    register-sw.js                                                             # SW-registratie (geen inline blob)
    util/  diamond.js  dom.js  logo.js  teams.js  time.js
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

1. **gate-job** (lichte deploy-gate): `uv sync --frozen` -> `ruff check` -> `pytest -q`. Geen node:test/Playwright — die draaien op push/PR in `ci.yml`; een cron-deploy gebruikt dezelfde commit met alleen verse data, en de render-stap valideert config en faalt luid. Blokkeert de build-job.
2. **build-job**: data-cache herstellen -> `honkbal fetch` -> `version.txt` schrijven -> `honkbal render` -> data-cache opslaan -> publicatie-artifact.

### `rebuild.yml` — geen fetch (handmatig)

Zelfde lichte gate-job. Build-job herstelt de data-cache (faalt luid als die ontbreekt) -> `honkbal render` -> publicatie-artifact. Bedoeld voor layout-/template-fixes zonder nieuwe data.

### `ci.yml` — volledige PR-gate

Draait op push naar `main` en bij pull requests: `uv sync --frozen` -> `ruff check` -> `pytest -q` -> node:test -> Playwright headless. Dít is het handhavingspunt voor frontend-regressies (code verandert bij PR/push, niet bij een cron-deploy). Geen publicatie.

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
2. De CLI (`cli.py` -> `_copy_static_assets`) kopieert het automatisch naar `docs/` bij de eerstvolgende render.
3. Let op: `frontend/js/sw.js` wordt naar `docs/sw.js` (root) gekopieerd; andere JS naar zowel `docs/js/` als de versioned root `docs/js/v/<asset_version>/`. Een nieuwe JS-module die een pagina laadt, hoort via `js_root` (versioned) te worden gerefereerd, niet via een kaal `/js/`-pad.

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

`honkbal/season.py` valideert het blok bij elke build: ongeldige datumstring (bijv. `30-02-2027`), ontbrekend verplicht veld of geschonden invariant (bijv. `ps > einde`) -> `ConfigError` -> build mislukt.

Controleer daarna: default-tab op de frontpage, datumkoppen in `debug.html`, output van `docs/debug.html`.

Controleer ook (enrichment): `honkbal/config/teams.py::TEAM_DIVISIONS` bij divisiewijzigingen en `honkbal/config/rivalries.py` voor nieuwe/vervallen rivalries. Hervalideer de FanGraphs-odds-veldnamen (SPEC §11.4) als de odds-adapter actief is.

## Bekende valkuilen

- **Kale `datetime.now()` in domeincode is verboden.** Gebruik altijd `clock.now()` — anders zijn tests niet deterministisch en is `--now` zinloos.
- **Config-validatie faalt de build hard.** Een seizoensblok met een typefout in een datum of een ontbrekend verplicht veld blokkeert render en publicatie. Dat is opzettelijk.
- **Service-worker cache-versie.** CSS en HTML worden **network-first** gehaald; toch moet de `CACHE`-naam in `sw.js` worden opgehoogd bij PRECACHE-wijzigingen, zodat verouderde pre-caches worden verwijderd.
- **`localStorage`-favorieten zijn browser-lokaal.** Testen in een andere browser of incognito geeft een andere uitkomst.
- **`localStorage`-score-cache is versiegebonden.** Bij wijzigingen in de datashape van `scores.js` de cacheversie in dat bestand ophogen, anders werken bestaande gebruikers met een incompatibele payload.
- **`config/feeds.py` (team-mapping + `ALLSTAR_FEED_ID`) is live gevalideerd op 2026-06-22** (30/30 teams + all-star, 0 mismatches). De feed-id's kunnen per seizoen veranderen; hervalideer met een live `discover_feeds`-run over range 105..161 bij twijfel of feed-wijzigingen.
- **`rebuild.yml` faalt luid** als er geen data-cache in Actions bestaat. Draai eerst `build.yml`.
- **`HONKBAL_NO_FETCH=1`** slaat fetch over en behoudt `.data/` ongewijzigd — handig bij lokale render-only iteraties.
- **`next_year` wordt legacy berekend** (voor de rollover, SPEC §4.3) — bewuste eigenaarsbeslissing, geen bug.
- **Enrichment faalt nooit de build.** Standings-fetch (`fetch/standings.py`) en odds-load (`fetch/playoff_odds.py`) falen zacht: ontbreken ze, dan dragen alleen de overige signalen bij en blijft `enrichment` evt. `None`. Enrichment draait **alleen vóór `season.windows.ps`**; in de postseason wordt het overgeslagen.
- **`config/rivalries.py` + `TEAM_DIVISIONS` zijn handmatig.** Divisie-indeling en rivalry-tiers staan hardcoded; controleer ze jaarlijks (her-/promotie-divisies, nieuwe rivalries) — zie "Jaarlijks onderhoud".
- **Playoff-odds-bron is nog niet bekabeld.** `load_playoff_odds` leest alleen `.data/playoff_odds.json` (genormaliseerd). Zolang geen adapter dat bestand schrijft, draagt het odds-signaal niets bij — enrichment werkt dan op rivalry/divisie/standen. FanGraphs-scrape-ontwerp: zie SPEC §11.4 en "Playoff-odds scrapen" hieronder.

## Wat je niet moet committen

- `docs/` (build-artifact, CI-verantwoordelijkheid)
- `version.txt` (CI-geschreven)
- `.data/` (fetch-cache; CI beheert via actions/cache)
- `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- `test-results/`, `playwright-report/`

## Playoff-odds scrapen (FanGraphs) — ontwerp

Het odds-signaal in enrichment leest een **genormaliseerd** bestand; de scraper is een aparte
adapter die dit bestand schrijft. Die scheiding is bewust: zo breekt een bronwijziging alleen de
adapter, niet de enrichment-regels.

**Stabiel contract — `.data/playoff_odds.json`:**

```json
{
  "fetched_at": "2026-06-24T19:00:00+02:00",
  "season": 2026,
  "teams": [
    {"team": "dodgers", "make_playoffs": 0.98, "win_division": 0.72, "win_world_series": 0.18}
  ]
}
```

`team` is een honkbal-slug (door `normalize_team`); kansen zijn `0..1`. `load_playoff_odds`/
`parse_playoff_odds` accepteren dit al (ook `%`-strings en `0..100`).

**Bron — FanGraphs playoff-odds-API (JSON, geen HTML-scrape nodig):**

- Endpoint: `https://www.fangraphs.com/api/playoff-odds/odds`
- Queryparams (te bevestigen): `projmode=combo` (projectiemodus), `standingsType=div`,
  optioneel `season=<jaar>`, `dateDelta=` (leeg = actueel).
- Respons: JSON-array van team-objecten. **De exacte veldnamen voor make-playoffs / win-division /
  win-WS moeten live worden geverifieerd** (FanGraphs hernoemt sleutels weleens) en daarna in een
  `_FG_FIELD`-mapping vastgelegd, met een teamnaam→slug-mapping zoals `fetch/standings.py` al heeft.

**Implementatieplan (adapter `fetch_playoff_odds(clock, data_dir, client)`):**

1. GET via `fetch/http.py::build_client` met een browser-achtige `User-Agent` (FanGraphs weert kale
   clients); respecteer de bestaande throttle, geen retry.
2. Map ruwe velden → genormaliseerde teams; sla het bestand atomisch op (zie standings als template).
3. **Faal zacht** (zelfde patroon als standings): bij HTTP-/parsefout een waarschuwing en de
   bestaande cache behouden; nooit de build blokkeren.
4. Wire in `cli_fetch.py` naast `fetch_standings`, óók alleen vóór `season.windows.ps`.
5. Test met een **gepinde, minimale** FanGraphs-JSON-fixture (publieke, gestripte payload — zie
   "Publieke repo-hygiëne"); geen live call in CI.

**Aandachtspunten:** FanGraphs-ToS/robots respecteren (lage frequentie, één call per build, caching);
de feed kan tussen seizoenen van vorm wijzigen → behandel de veld-mapping als jaarlijks-onderhoud-
item (SPEC §11.4). Alternatieve bron als FanGraphs dichtgaat: MLB-StatsAPI heeft geen kant-en-klare
playoff-odds, dus dan is FanGraphs of Baseball-Reference de praktische keuze.

## Referenties

- **SPEC.md** — normatief contract voor alle gedrag
