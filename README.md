# Honkbal.net

Honkbal.net is een Python/uv static-site generator die het MLB-speelschema weergeeft in Nederlandse tijd (Europe/Amsterdam). De site bestaat volledig uit statische HTML-bestanden gegenereerd door een Python-buildpipeline.

## Wat de site doet

- Speelschema per dag in Amsterdam-tijd, met filters per dagdeel (ochtend/avond/nacht/alles) en per team.
- Postseason-verrijking via ESPN-API: wedstrijdtitel, seriestand, "wordt alleen gespeeld als nodig"-markering.
- Live scores via de officiële MLB Stats API (client-side, geen server).
- Standen (MLB Stats API, 5 views: divisie, league, wildcard, enz.) met favorieten-highlight.
- Favoriete teams: opgeslagen in `localStorage`, geen server-side profiel.
- Offline-modus via service worker (network-first voor HTML/CSS, cache-first voor afbeeldingen).
- "Meer laden"-knop: de eerste 250 wedstrijden staan inline; de rest wordt on-demand geladen uit `<pagina>.tail.json`.

## Tech stack

- **Python ≥3.12 + uv** — dependency management, CLI, testsuite
- **Jinja2** — HTML-templating (autoescape aan)
- **httpx** — HTTP-client voor fetch
- **Pydantic v2** — getypte datamodellen + config-validatie
- **pytest + ruff** — tests en lint
- **Vanilla ES-modules** — scores, standen, favorieten, service worker (geen bundler)
- **node:test + Playwright** — frontend unit- en integratietests
- **GitHub Actions** — CI/CD

## Snel starten

```bash
# Vereisten: Python >=3.12, uv (https://docs.astral.sh/uv/), Node 20+

uv sync          # Python-deps installeren
npm ci           # frontend-devdeps (Playwright) installeren

uv run pytest -q           # Python-tests
uv run ruff check .        # lint
npm run test:unit          # frontend unit-tests (node:test)
npm run test:e2e           # frontend DOM/offline (Playwright)

uv run honkbal fetch       # MLB-data ophalen -> .data/
uv run honkbal render      # HTML renderen -> docs/
uv run honkbal build       # fetch + render in een stap
```

Open `docs/index.html` in een browser om het resultaat te bekijken.

## Repository-structuur

```
honkbal/           Python-pakket: clock, config, fetch, parse, render, templates, CLI
frontend/          Vanilla JS (ES-modules), CSS, statische assets (logos, favicon, manifest)
tests/             Python-tests: unit, integration, golden snapshots
frontend/test/     node:test frontend unit-tests
frontend/e2e/      Playwright DOM/offline/SW-tests
.github/workflows/ build.yml (cron+publicatie), rebuild.yml (no-fetch), ci-python.yml (PR-gate)
SPEC.md            Normatief contract
```

## CI/CD

De site wordt uitsluitend via GitHub Actions gebouwd en gepubliceerd. `docs/` en `version.txt` worden door de workflows gegenereerd en staan in `.gitignore` — niet handmatig committen.

- **`build.yml`**: draait op schema (meerdere keren per dag tijdens het seizoen) en handmatig. Voert lint + alle tests uit als gate, haalt daarna data op, rendert en publiceert de statische output.
- **`rebuild.yml`**: handmatig — rendert opnieuw zonder een nieuwe datafetch (vereist dat er een data-cache in Actions aanwezig is).
- **`ci-python.yml`**: PR-gate — lint + Python-tests bij elke push naar `main` en bij pull requests.

## Bijdragen

Lees `CLAUDE.md` voor de werkhandleiding (key commands, repo-layout, valkuilen). `SPEC.md` is het normatieve contract voor alle functionaliteit.

Minimale validatie voor elke wijziging:

```bash
uv run ruff check .
uv run pytest -q
npm test
uv run honkbal render   # controleert of docs/ correct wordt gegenereerd
```

Bump bij wijzigingen aan `frontend/js/sw.js` (PRECACHE of cache-strategie) altijd de `CACHE`-naam in dat bestand.
