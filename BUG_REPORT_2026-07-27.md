# Bug- en privacyreview — commits van 27 juli 2026

## Scope

Beoordeeld in tijdzone `Europe/Amsterdam`:

- `fed82ab` — grace-window en live-sectie
- `3d7bcf1` — bètafeatures en interessefilter
- `f57e534` — merge van bovenstaande featurelijn
- `08f9744` — visuele integratie interessefilter
- `fdee1c8` — poll-vensters voor de live-sectie
- `466877e` — documentatie-update

De mergecommit is op beide ouderlijnen beoordeeld zonder dezelfde wijziging dubbel als bevinding
te tellen. De uiteindelijke toestand op `466877e` is daarnaast als geheel gecontroleerd.

## Bevindingen

### 1. [Middel] Live-bèta hernoemt ook de topnavigatie van “schema”

**Geïntroduceerd in:** `3d7bcf1`

`applyNuAvondLabel()` loopt over alle `.nav-link`-elementen en vervangt de tekst van elke link
waarvan de URL `/avond.html` bevat. Zowel de topnavigatielink “schema” in
`honkbal/templates/nav.html` als de avond-tab in `honkbal/templates/subnav.html` verwijst naar die
URL. Met de live-bèta aan worden daardoor beide labels “nu + avond”, terwijl SPEC §6.8 alleen het
navigatielabel van de avond-tab laat wijzigen.

**Gevolg:** de primaire navigatie verliest het label “schema” en toont twee gelijknamige links.

**Waarom de test dit mist:** de unit-test maakt slechts één `/avond.html`-link met tekst “avond”
aan en modelleert de gelijktijdig aanwezige topnavigatielink niet.

**Aanbevolen oplossing:** selecteer alleen de link in de schedule-subnav, bijvoorbeeld via een
specifieke container/data-hook, en voeg een test toe met zowel “schema” als “avond”.

### 2. [Middel] Deduplicatie kan de verkeerde wedstrijd van een doubleheader verbergen

**Geïntroduceerd in:** `fed82ab`

`syncHiddenRows()` identificeert een statische rij uitsluitend met
`away-team|home-team` en verbergt vervolgens de eerste overeenkomst in DOM-volgorde. Bij twee
wedstrijden met dezelfde teams kan niet worden bepaald welke wedstrijd live is. Als game 2 live
is terwijl game 1 door de vieruurs-grace nog zichtbaar is, wordt game 1 verborgen en blijft de
statische rij van game 2 naast de live-rij staan.

**Gevolg:** de live-sectie dedupliceert de verkeerde rij en toont de actuele wedstrijd dubbel.

**Waarom de test dit mist:** de doubleheader-test controleert alleen dat precies één van twee
gelijke rijen wordt verborgen, niet dat dit de rij van de live wedstrijd is.

**Aanbevolen oplossing:** render een stabiele wedstrijdidentificatie (`gamePk` indien in beide
bronnen beschikbaar, anders datum/starttijd plus teams) op de statische rij en match daarop.

### 3. [Laag] Preview/warmup/delayed-wedstrijden doorbreken “favoriet eerst”

**Geïntroduceerd in:** `fed82ab`

De live-lijst wordt met `sortLive()` gesorteerd, maar de preview-lijst wordt niet gesorteerd.
`renderScoresHtml()` rendert bovendien alle previews vóór alle live-wedstrijden. Daardoor kan een
niet-favoriete warmup of delayed game boven een favoriete live game staan. Dit wijkt af van het
contract “sortering (favoriet eerst)” in SPEC §6.8.

**Gevolg:** favorieten staan in de “nu bezig”-sectie niet betrouwbaar bovenaan.

**Aanbevolen oplossing:** sorteer de gezamenlijke live/preview-set eerst op favoriet en pas daarna
op de gewenste status-/inningvolgorde; leg de combinatie preview + favoriete live game vast in een
test.

### 4. [Laag] `AGENTS.md` en `CLAUDE.md` zijn niet langer parallel

**Geïntroduceerd/verergerd in:** `fed82ab`, `3d7bcf1`, `fdee1c8`, `466877e`

De repositoryhandleiding zegt dat `AGENTS.md` inhoudelijk parallel is aan `CLAUDE.md`, maar de
commits van vandaag werkten alleen `CLAUDE.md` bij. `AGENTS.md` mist onder meer de grace-window,
live-pollvensters, bètafeatures, versioned module-root en de bijbehorende valkuilen.

**Gevolg:** agents krijgen afhankelijk van hun instapbestand verschillende werkinstructies en
kunnen nieuwe code verkeerd onderhouden.

**Aanbevolen oplossing:** spiegel de relevante documentatiewijzigingen naar `AGENTS.md` of maak
één bestand expliciet de bron en laat het andere ernaar verwijzen.

## Controle op gevoelige informatie

### Bronbestanden en Git-history

- Gitleaks op de wijzigingen van vandaag: **geen secrets gevonden**.
- Gitleaks op de volledige bereikbare Git-history: **geen secrets gevonden**.
- Aanvullende patrooncontrole op private keys, gangbare cloud-/GitHub-/Slack-/OpenAI-tokens,
  bearer tokens, lokale homepaden en e-mailadressen in de worktree: **geen gevoelige waarde in
  tracked bronbestanden gevonden**.
- De afwijkende URL-scan vond alleen publieke project-, documentatie-, font-, test- en
  databron-URL’s.
- `.claude/settings.local.json` bestaat lokaal, maar is **niet tracked** en wordt door `.gitignore`
  genegeerd.

### Commitmetadata

**Privacy-aandachtspunt:** de commits van vandaag bevatten een niet-gemaskeerd author/committer-
e-mailadres met een lokale hostnaam. Dat is geen secret in een bronbestand en Gitleaks markeert
het terecht niet als credential, maar het wordt wel onderdeel van de publieke Git-history en
onthult persoonlijke/lokale identiteitsinformatie. De concrete waarde is bewust niet in dit
rapport overgenomen.

**Aanbevolen oplossing:** configureer voor toekomstige commits een GitHub-noreply-adres. Als de
metadata niet publiek mag blijven, is history rewriting nodig; behandel dat als een afzonderlijke,
expliciet goedgekeurde operatie omdat commit-hashes en gedeelde branches daardoor wijzigen.

## Uitgevoerde validatie

- `uv run ruff check .` — geslaagd
- `uv run pytest -q` — 193 geslaagd
- `npm run test:unit` — 131 geslaagd
- `npm run test:e2e` — 17 geslaagd

De groene suite weerlegt de bovenstaande bevindingen niet: de betrokken combinaties en de
volledige navigatie- en documentatiestructuur worden momenteel niet door regressietests afgedekt.
