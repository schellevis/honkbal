# Honkbal.net v2 — Functioneel Contract & Specificatie

**Status:** normatief contract voor de Python/uv-herbouw.
**Laatste herziening:** 2026-06-21.

Dit document is de **bron van waarheid** voor v2. Het beschrijft het *gewenste* gedrag — niet
klakkeloos het gedrag van de huidige PHP-code. Waar v2 bewust afwijkt van de legacy, staat dat
expliciet gemarkeerd. Een implementatie is "klaar" als ze dit contract haalt én de
acceptatietests in §12 slagen.

## Normatieve statustags

Elke gedragsregel die ertoe doet, draagt één van:
- **[LEGACY]** — gedrag van de huidige site dat v2 ongewijzigd overneemt.
- **[FIX]** — een bug in de legacy die v2 bewust repareert naar bedoeld gedrag.
- **[NEW]** — nieuw v2-gedrag/kwaliteitseis zonder legacy-equivalent.
- **[DROP]** — legacy-functionaliteit die in v2 vervalt.

---

## 0. Referentieomgeving (verplicht, [NEW])

Alle acceptatietests en golden fixtures draaien tegen één vastgepinde omgeving:
- **Tijdzone build/logica:** `Europe/Amsterdam`.
- **"Nu"** wordt geïnjecteerd (niet `datetime.now()` direct), zodat tests een vaste klok kunnen zetten.
- **Inputfixtures:** vastgepinde `all.csv`-achtige schedule-fixtures + vastgepinde ESPN-API-JSON
  fixtures in de testsuite. Geen live netwerkcalls in tests.
- **Browserstate:** lege `localStorage`/lege service-workercache als uitgangspunt voor frontend-tests.
- **Golden output:** een ESPN-tv-gids-vrije schedule-render (dat is óók wat de huidige productie
  oplevert) dient als golden snapshot voor de delen die v2 *niet* bewust wijzigt. Vergelijking
  gebeurt op een **genormaliseerd wedstrijdmodel + relevante DOM-fragmenten**, niet op volledige
  HTML-bytes (buildtijd en assetversies zijn bewust variabel).

---

## 1. Doel en scope

Statische website voor Nederlandse MLB-kijkers: MLB-speelschema's omgerekend naar
`Europe/Amsterdam`, een client-side scorepagina, standen, en browser-lokale favorieten.
Geen backend, geen database. Build = data ophalen → normaliseren → HTML renderen → naar
statische output.

**In scope (v2):**
- Schema-pagina's (avond/ochtend/nacht/alles + per team) met seizoens- en filterlogica.
- **Postseason-verrijking via de ESPN-API** (ronde-labels + serie-stand). **[LEGACY, behouden]**
- Client-side scores en standen via de MLB Stats API. **[LEGACY, behouden]**
- Favorieten (localStorage), settings-pagina, service worker, debug-pagina.

- Tv-gids: ESPN-zenderlogo's bij uitgezonden wedstrijden (§3.3, herleefd op nieuwe bronnen). **[REVIVED]**

**Uit scope / [DROP]:**
- De legacy-tv-gids-implementatie (`gids-grab`, `gids-read`, `espn.json`, `simple_html_dom`,
  espn.nl-HTML-scraping): vervangen door §3.3 (ESPN watch-API + tvgids.nl-JSON-fallback).
- Backend-/publicatiescripts en externe-serviceconfig buiten deze generator.

**Uitgelichte wedstrijden ([NEW], geïmplementeerd):** regelgebaseerde "interessantheid" per
wedstrijd. Het genormaliseerde wedstrijdmodel (§3.1) heeft een optioneel verrijkingsveld dat een
losse build-stap (`honkbal/enrichment.py`) vult; tonen in de renderlaag volgt later (zie §11).

Tijdzones:
- MLB-schedule bron-parsing: `America/New_York` → omgerekend naar `Europe/Amsterdam`. **[LEGACY]**
- ESPN-API postseason-tijden: bron UTC → `Europe/Amsterdam`. **[LEGACY]**
- Alle weergave + hoofdlogica: `Europe/Amsterdam`. **[LEGACY]**

---

## 2. Pagina's en navigatie

Gerenderde statische bestanden in `docs/`:

| Bestand | Inhoud |
|---|---|
| `index.html` | Landing; standaardtab afhankelijk van seizoen (§5.1) |
| `avond.html` / `ochtend.html` / `nacht.html` / `alles.html` | Schema met tijdfilter (§5.2); eerste batch inline + "meer laden" (§5.9) |
| `<team>.html` | Eén team, alle wedstrijden (geen tijdfilter); eerste batch inline + "meer laden" (§5.9) |
| `<pagina>.tail.json` | **[NEW]** Per schemapagina: kant-en-klare HTML-rijfragmenten voorbij de eerste batch, voor "meer laden" (§5.9) |
| `scores.html` | Client-side scores (MLB Stats API) |
| `standings.html` | Client-side standen (MLB Stats API) |
| `settings.html` | Favoriete teams instellen (localStorage) |
| `debug.html` | Operationele timestamps |
| `offline.html` | Skeleton-fallback voor service worker |
| `404.html` | Statisch |

Topnavigatie: **schema** → `/` (de voorpagina, met de default-tab van §5.1), **scores** → `scores.html`, **standen** →
`standings.html`, **instellingen** (tandwiel) → `settings.html`. Sub-pills op schema-pagina's:
**avond / ochtend / nacht / alles**. Daarboven een team-`<select>` (alfabetisch) die naar
`<team>.html` navigeert. H1 = `⚾ honkbal.net`; op scores een status-indicator (refresh-icoon +
laatste-update-tijd).

**[NEW] HTML-kwaliteit:** geldige HTML5, `lang="nl"`, correcte `<body>`/`<form>`-structuur (de
legacy-fouten — `<div>` vóór `<body>`, dubbele/onvolledige `</body>`, losse `</form>` — worden
**niet** nagebootst). Alle dynamische/externe tekst (team-namen, ESPN-`descr`) wordt
HTML-geëscapet.

---

## 3. Datamodel en pijplijn (build-time)

### 3.1 Genormaliseerd wedstrijdmodel [NEW]
Eén intern model (typed dataclass/pydantic), bron voor alle rendering:

```
Game:
  date_ams:    date        # speeldatum in Europe/Amsterdam
  time_ams:    time | None  # starttijd in Amsterdam; None = TBD
  hour_ams:    int | None   # startuur 0..23 (None bij TBD)
  date_et:     date         # kalenderdatum in America/New_York (= legacy "old")
  away:        str          # away-team (origineel "Away at Home")
  home:        str          # home-team
  is_tbd:      bool
  source_seq:  int          # [NEW] bron-volgnummer (fetch-/CSV-volgorde); tiebreaker bij een
                            #       identieke dedup-sleutel — zie dedup-regel hieronder
  enrichment:  Enrichment | None   # [NEW] regelgebaseerde interessantheidsscore (§11); None bij postseason/niet-MLB
ScheduleMeta:
  modified:  datetime       # nieuwste Last-Modified uit bron-headers
  refreshed: datetime       # moment van fetch
```
**[FIX] Sortering:** wedstrijden worden gesorteerd op `(date_ams, time_ams)` met TBD achteraan
binnen de dag (legacy sorteerde alleen op dag → onbepaalde volgorde binnen een dag).
**[FIX] Identiteit/dedup (pariteits-collapse):** de schedule-fetch concateneert de feeds van
**beide** teams, dus een normale wedstrijd komt **tweemaal** identiek binnen (één keer per team).
v2 dedupliceert daarom met een **pariteits-collapse**: tel per sleutel
`(date_ams, time_ams, date_et, away, home, is_tbd)` het aantal bronregels `n` en behoud er
`ceil(n/2)` (de eerste in bronvolgorde). Een normale wedstrijd (`n=2`) → 1 rij; een
TBD-doubleheader die via beide feeds 4× binnenkomt (`n=4`) → 2 rijen blijven behouden. Botsingen
worden dus **niet stil overschreven**: een echte doubleheader overleeft.
`source_seq` (het **bron-volgnummer**, zie modelveld) is de tiebreaker bij gelijke sleutel en
bepaalt welke rij van een paar behouden blijft (laagste seq eerst).
- **Aanname:** elke echte wedstrijd verschijnt een **even** aantal keer in de gecombineerde feed
  (normaal 2×, TBD-DH 4×). `ceil(n/2)` is alléén correct onder die pariteitsgarantie — een derde
  feed of een oneven aantal `>1` zou spookduplicaten opleveren. De huidige fetch-scope (30 teams +
  all-star) garandeert de pariteit; bij scope-uitbreiding moet deze strategie heroverwogen worden.
  De aanname is geborgd met `test_dedupe_pariteit_*`.
- De CSV biedt **geen** stabiele event-id; vandaar de pariteits-collapse op de schedule-velden
  i.p.v. dedup op een event-id. Het modelveld `source_seq` blijft de tiebreaker-/identiteitsdrager.

### 3.2 MLB-schedule ophalen + normaliseren [LEGACY-gedrag, herbouw]
- **Fetch [FIX — scope versmald]:** GET
  `https://www.ticketing-client.com/ticketing-client/csv/GameTicketPromotionPrice.tiksrv`
  met params: `team_id`, `display_in=singlegame`, `ticket_category=Tickets`,
  `site_section=Default`, `sub_category=Default`, `leave_empty_games=true`, `event_type=T`,
  `year=<huidig jaar>`, `begin_date=<YYYYMMDD vandaag>`. Throttle tussen calls (config).
  Headers per team bewaard voor `modified`.
  - **[FIX]** v2 haalt **alléén de 30 MLB-teams (NL+AL) plus de all-star-pseudo-feed** op, **niet**
    de volledige `team_id`-range 105..161 met minor-league affiliates (legacy). Reden: de
    affiliate-responses zijn ruis die toch door de allowlist werd weggefilterd; elke MLB-wedstrijd
    zit al in het schema van minstens één van de 30 teams. De **all-star-feed blijft expliciet
    behouden**, want `AL All-Stars at NL All-Stars` komt mogelijk niet via een van de 30 teams
    binnen.
  - **Prerequisite — eenmalige feed-ontdekking (Fase 2):** legacy itereerde blind over de numerieke
    range, dus de `team_id ↔ team`-mapping bestaat nog niet. v2 stelt die **één keer** vast met een
    diagnostische run die de **volledige range 105..161** ophaalt, per `team_id` de feed parseert en
    vastlegt welke `team_id` welk team levert (en welke alléén minor-league/lege/ongeldige feeds
    geven). Output = een **gecommitte mapping** (`config`-data): de geldige `team_id`'s van de 30
    MLB-teams + het `team_id` van de all-star-pseudo-feed. De **recurrente build** gebruikt daarna
    enkel die gemapte feeds.
    - Dit is een **eenmalige/handmatige diagnostiek**, geen onderdeel van de dagelijkse build. Bij
      twijfel of feed-wijzigingen kan de run herhaald worden om de mapping te hervalideren.
    - Lukt de mapping niet betrouwbaar, dan is de fallback de legacy-range 105..161 + allowlist
      (§4.2) — maar het doel is de versmalde scope.
- **Parse:** kolommen `START DATE` (m/d/y), `START TIME ET` (H:i A, kolom index 2), `SUBJECT`
  (game = `"Away at Home"`). Getimede regels: parse datum+ET-tijd in `America/New_York` →
  `date_et` = NY-kalenderdatum; converteer naar Amsterdam → `date_ams`/`time_ams`/`hour_ams`.
  TBD-regels: `is_tbd=True`, `time_ams=None`; `"  - Time TBD"` uit naam gestript.
  - **[LEGACY-gedrag, robuuste herimplementatie]** TBD-detectie op expliciete aanwezigheid van de
    tekst "Time TBD". De legacy `stripos(...) != 0` (`put.php:71`) levert voor de echte feed de
    **juiste** uitkomst (geen wedstrijd begint met "Time TBD", dus positie is nooit 0); v2 behoudt
    diezelfde uitkomst maar codeert de check expliciet/robuust i.p.v. via PHP-`stripos`-typegedrag.
    Geen waarneembaar gedragsverschil.
  - **[FIX]** TBD-regels worden óók in `America/New_York` geïnterpreteerd, consistent met getimede
    regels (legacy gebruikte daar Amsterdam — bron van datuminconsistentie). `date_et` en
    `date_ams` worden voor TBD identiek afgeleid uit de NY-kalenderdatum.
- **Filter:** alleen wedstrijden met start `> nu − LIVE_GRACE_HOURS` (toekomstige wedstrijden plus
  wedstrijden die vermoedelijk nog bezig zijn; `LIVE_GRACE_HOURS = 4` in `config/toggles.py`).
  **[FIX — was `> (nu − 1 dag)` in legacy; daarna strikt `> nu`; nu een grace-window zodat een
  reeds begonnen wedstrijd zichtbaar blijft zolang die redelijkerwijs nog loopt]**
  Getimede regels: moment-nauwkeurig (`start > nu − grace`). TBD-regels (geen starttijd):
  datum-granulair (`date_ams >= vandaag`), want zonder tijd valt niet te bepalen of een wedstrijd
  vandaag al voorbij is.
  **Let op:** dit filter is build-time en dus een momentopname; de gepubliceerde pagina blijft
  daarna uren staan (buildcadans §8). De browser past hetzelfde filter opnieuw toe op de
  gerenderde rijen (§6.10), zodat een reeds afgelopen wedstrijd niet tot de volgende build
  blijft staan.
- **Allowlist (render-guard):** alleen renderen als away **of** home een bekend MLB-team is (of een
  all-star pseudo-team). Zie §4.2. **[LEGACY]** (in legacy heette de allowlist-array verwarrend
  `extrateams`). Door de versmalde fetch-scope is dit niet meer de primaire affiliate-filter, maar
  blijft het de render-guard tegen niet-MLB-tegenstanders (bv. spring-training-exhibities).
- **[NEW] Fetch-robuustheid (last-known-good):** schrijf per bron eerst naar tijdelijke data en
  valideer die; vervang de last-known-good-cache pas **atomair** na succes. Een fetch geldt als
  mislukt als het aantal succesvolle team-responses onder een minimumdrempel ligt (drempel relatief
  aan de versmalde scope: de 30 MLB-teams + all-star-feed, niet de oude 57); bij mislukking
  blijft de vorige cache intact (geen lege/gedeeltelijke dataset overschrijft een goede).
  `ScheduleMeta.modified` = nieuwste geldige `Last-Modified`; ontbreekt die voor álle responses, dan
  `modified = refreshed` (fetch-moment).

### 3.3 ESPN-tv-uitzendgids [REVIVED — nieuwe bronnen]
**Doel:** bij wedstrijden die ESPN Nederland uitzendt het zenderlogo (espn/espn2/espn3/espn4)
in de schemarij tonen, met een "NL"-badge bij Nederlands commentaar. ESPN Extra is **bewust
uitgesloten** (eigenaarsbeslissing): airings op `nl_espn_extra` worden in de adapter gedropt.
De legacy-implementatie (espn.nl-HTML-scrape) is vervallen; dit is de herbouw op JSON-bronnen.

**Bronketen (adapter `fetch/tv_guide.py`, patroon = playoff-odds §11.4):**
- Primair: ESPN watch-GraphQL-API (`watch.graph.api.espn.com/api`), één GET per dag over
  `tv_guide_days` dagen (vandaag t/m +3), variabelen `countryCode=NL`, `type=UPCOMING`,
  `day` + `tz` in Amsterdam-lokale tijd (DST-afhankelijk afgeleid). Er is géén
  categoryId-filter in de query: de adapter filtert client-side op `subcategory`/`league`
  == "MLB", zodat er geen categorie-constante te onderhouden valt. ESPN telt pas als mislukt
  wanneer **alle** dagcalls falen — een dag zonder MLB-uitzendingen is legitiem.
- **apiKey-zelfherstel:** de `apiKey` is een publieke client-side constante uit de
  espn.nl-paginabundel (geen secret; live gevalideerd 2026-08-05) die kan roteren. De fetch
  geeft voorrang aan `.data/espn_watch_config.json`; dat bestand wordt geschreven door
  `npm run discover:espn` (`frontend/tools/discover-espn-watch.mjs`): Playwright laadt de
  speelkalender headless (de pagina zelf zit achter botmitigatie), kijkt het API-request af
  en valideert de key vóór het wegschrijven. `build.yml` draait dit automatisch wanneer de
  vorige fetch niet (meer) op bron `espn` draaide; de constante in de code is de fallback.
- Fallback: tvgids.nl-JSON (`json.tvgids.nl/v4/programs/?day=0..3&channels=148,468,469,470`;
  148=ESPN1, 468=ESPN2, 469=ESPN3, 470=ESPN4). Beide payloadvormen (dict per
  kanaal-id en lijst met `ch_id`) worden geaccepteerd. Alleen titels die op een wedstrijd wijzen
  tellen mee (teamscheider "X vs Y"/"X - Y", postseason-/all-star-aanduiding, de generieke
  titel "Major League Baseball" of "Bases Covered"); magazineprogramma's ("MLB Quick Pitch")
  vallen af.
- **Bases Covered-teambron:** "MLB Bases Covered Live" (whip-around, op ESPN NL en o.a. de
  BBC) volgt één hoofdwedstrijd met doorschakelingen naar andere stadions, maar de ESPN-feed
  levert er geen teampaar bij (alle kandidaatvelden null; live geverifieerd 2026-08-16).
  Voor teamloze airings met deze titel haalt de fetch éénmalig (throttled, soft-fail) de
  MLB.com-pagina `mlb.com/international/europe/bases-covered-live` op, die per uitzenddatum
  de hoofdwedstrijd noemt ("Sunday, August 16: New York Yankees vs Toronto Blue Jays @ …"),
  en vult het teampaar per datum in. Daarna matcht de airing via de gewone teampass; mislukt
  de call of ontbreekt de datum, dan blijft de airing teamloos (conservatieve tijdpass).

**Genormaliseerd contract — `.data/tv_guide.json`** (stabiel; bronwijziging breekt alleen de
adapter): `fetched_at`, `season`, `source` (`espn`|`tvgids`) en `airings[]` met per airing
`channel` (kanaalslug), `start`/`end` (ISO-8601, Amsterdam), `teams` (honkbal-slugs via
`normalize_team`, `[]` indien onbekend), `nl_commentary` (bool; tolerant gedetecteerd uit
titel/feedName: `(NL)`, "Nederlands(talig) commentaar", "NL-commentaar", feedName die als geheel
"NL" is — een kale "NL" in de titel telt bewust níét: "NL All-Stars"), `live` (replays `false`)
en `title` (ruw, alleen debug). **Carry-over:** airings uit de vorige cache waarvan de start
binnen `[nu − live_grace_hours, nu]` ligt blijven behouden (dedup op kanaal + start ±5 min),
zodat een lopende wedstrijd zijn logo houdt bij een build midden in de wedstrijd.

**Zacht falen:** beide bronnen stuk → waarschuwing, bestaande cache blijft, build faalt nooit.
Fetch draait binnen `showfrom <= nu < einde` — bewust dóór de postseason heen.

**Matching (render-time, `honkbal/tv_guide.py::build_tv_lookup`):** alleen airings met
`live=true`; elke airing matcht hoogstens één wedstrijd.
1. **Teampass:** ongeordende teamset-gelijkheid én `|game-start − airing-start| ≤
   tv_match_tolerance_min` (75 min); kleinste verschil wint (doubleheaders); een al gematchte
   wedstrijd houdt zijn eerste kanaal (simulcast).
2. **Tijdpass** (teamloze airings, m.n. tvgids/all-star): alleen toewijzen als **precies één**
   nog niet-gematchte getimede wedstrijd binnen de tolerantie valt; bij ambiguïteit géén logo.
TBD-wedstrijden matchen nooit; replays vallen dubbel af (`live=false` + tijdtolerantie).

**Render:** gematchte rij krijgt vooraan de cel
`<div class="espn" data-channel="<slug>"[ data-nlcom="1"]>[<span class="comm">NL</span>]<logo></div>`
met het logo als `/img/espn/<slug>.png?<asset_version>` (+ dark-variant via `<picture>` indien
aanwezig; geen height-attribuut — breedte per kanaal komt uit CSS). Ontbrekend asset of geen
match → geen div. Client-side zichtbaarheidsinstellingen: §6.11.

### 3.4 tvgids.nl [REVIVED als fallback]
In legacy dode code; in v2 uitsluitend de fallback-bron binnen §3.3 (zelfde genormaliseerde
output; geen `nl_commentary`-detectiebron).

### 3.5 ESPN-API postseason-verrijking [FIX — heractivatie]
**Doel:** postseason-rijen verrijken met ronde-label (bv. "ALCS Game 1\*") en serie-stand (bv.
"(2-1)"). Alleen relevant/actief wanneer `nu >= start.ps`.
> **Status:** postseason-verrijking is een expliciete build-stap. Norm = de ESPN-**fixtures** in
> de testsuite.
> **Dedup/conflict:** hetzelfde event komt via meerdere teamschema's binnen. De `PostseasonData.games`
> zijn een lookup op `(date_ams, hour_ams, home_team_name)` (zie model hieronder); diezelfde
> lookup-sleutel fungeert als dedup-sleutel (**eerste wint**; identieke payload verwacht). `event_id`
> wordt wél bewaard per game (voor de serie-stand), maar is geen dict-sleutel en dus niet de
> dedup-sleutel. In de praktijk equivalent zolang geen twee verschillende events dezelfde
> `(date_ams, hour_ams, home)` delen — wat normaal niet gebeurt.

- **Fetch schedules:** per ESPN-team-abbreviatie (`team_abbr`, 30 stuks, §4.3) GET
  `https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams/<abbr>/schedule`.
- **Caching [FIX-doc]:** herverwerk alleen als `nu − parsed.date >= espncap`. `espncap` is in
  **seconden** (3000 s ≈ 50 min); de legacy-comment "minuten" was fout — v2 documenteert het als
  seconden en maakt het een benoemde config-waarde.
- **Per event:** parse `competition.date` (`%Y-%m-%dT%H:%MZ`, UTC) → Amsterdam. Voor toekomstige
  events: GET `.../summary?event=<id>` en cache als `espnapi/<id>.json`.
  `descr` = `competition.notes[].headline` met `" If Necessary"` → `"*"`.
  Teamnaam-normalisatie `"Diamondbacks"` → `"D-backs"`.
- **Parsed model [NEW intern, gedrag = legacy]:**
  ```
  PostseasonData:
    fetched_at: datetime
    teams:  dict[abbr -> shortDisplayName]
    games:  dict[(date_ams, hour_ams, home_team_name) -> PostseasonGame]
  PostseasonGame: { event_id, record, descr, home, away }
  ```
  (Legacy nesting `espnapi_parsed.json[games][Y-m-d][H][homeName]` blijft inhoudelijk gelijk;
  intern als getypte lookup.)
- **Serie-stand parsing [LEGACY]:** uit `espnapi/<id>.json` → `seasonseries[type=="current"].summary`.
  - `"Series tied X-Y"` → toon `(X-Y)`.
  - anders `"<team> lead(s) series X-Y"` → oriënteer score zodat away-team-wins eerst staan
    (vergelijk `teams[winnaar]` met away/home).
  - **[NEW]** onbekende/afwijkende `summary`-tekst → geen stand tonen (geen crash).

---

## 4. Configuratie (`config`-equivalent)

### 4.1 Toggles [LEGACY waarden]
- `show_games = 250` **[FIX]** → **[NEW: betekenis gewijzigd]**: dit is nu de **inline beginbatch**
  per schemapagina (eerste 250 wedstrijden in de HTML), géén harde cap meer op wat bereikbaar is.
  De rest is bereikbaar via "meer laden" (§5.9). Legacy leverde door een off-by-one feitelijk 249;
  v2 zet de inline batch op exact **250**. Teampagina's gebruiken dezelfde beginbatch + "meer laden"
  (in de praktijk past één team meestal binnen 250 → tail leeg).
- `load_more_batch = 250` **[NEW]**: stapgrootte per "meer laden"-klik (gelijk aan de beginbatch).
- `sleep_seconds = 2`, `grab_no_wait = false`.
- `espncap = 3000` (seconden, §3.5).
- `countdown_from = "01-01"` (vanaf welke dag-maand de opening-day-countdown tonen).
- `live_grace_hours = 4` **[NEW]**: getimede wedstrijden blijven tot dit aantal uren na hun
  starttijd in de gerenderde schema's staan (vermoedelijk nog bezig, §3.2).
- `tv_guide_days = 4` **[NEW]**: aantal dagen tv-gids vooruit ophalen (§3.3).
- `tv_match_tolerance_min = 75` **[NEW]**: max. verschil tussen wedstrijd- en uitzendingsstart
  bij het matchen (§3.3).
- ~~`espnpsmatchtimes`~~ **[DROP]** (legacy tv-gids-matching; v2 matcht per §3.3).
- ~~`espnmatchtvgidsinps`~~ **[DROP]** (legacy tvgids.nl-fallbackgedrag).

### 4.2 Teamlijsten
- `teams_nl` (15 NL-teams), `teams_al` (15 AL-teams). Allowlist `mlb_teams = teams_nl + teams_al`.
- Pseudo-teams `extra = ["national league","american league","al all-stars","nl all-stars"]`
  (voor all-star games). `allowlist_render = mlb_teams + extra` (legacy `extrateams`).
  **[FIX]** Legacy had hier `"all all-stars"` — een typo; de feed bevat `AL All-Stars at NL
  All-Stars` (`all.csv`). v2 gebruikt `"al all-stars"`; beide all-star-kanten worden
  genormaliseerd, ge-allowlist én gelogo'd.

### 4.3 Seizoenstabel + actief-seizoen-bepaling
Per jaar (`%d-%m-%Y`). **Verplicht:** `reg`, `showfrom`, `einde`, `ps`, `wc`, `ds`, `cs`, `ws`,
`new`, `hide`. **Optioneel:** `allstargame` (ontbreekt bv. in het 2024-blok), `newreg` (next-season
reguliere start — mag **onbekend/None** zijn, zie §5.3), `uitzondering[]` (codes `dm`+away+home).
`team_abbr` = 30 ESPN-abbreviaties. `dagen` (1-7 → ma..zo), `maanden` (01-12 → NL-namen).

Actief-seizoen-algoritme **[LEGACY, met FIX]**:
1. `year` = huidig jaar (`+1` als `test_next_season`).
2. **[LEGACY, behouden]** `next_year = year + 1` wordt berekend **vóór** de fallback/rollover (stap
   3-4), op basis van het kalenderjaar — exact zoals `config.php:198`. Gevolg: na een rollover (stap
   4) kan `next_year == year` zijn (bv. op 15-12-2025 → `year` rolt naar 2026, `next_year` blijft
   2026). Dit is een bewuste keuze om het huidige sitegedrag te reproduceren; zie Appendix A.
3. Als geen `start[year]`-**blok** bestaat → `year -= 1`. **[FIX]** v2 toetst op de aanwezigheid
   van het jaarblok (niet, zoals legacy, op de `reg`-key); zie Appendix A.
4. Als `nu >= start[year].einde` → `year += 1`.
5. Projecteer alle datums van `year` naar het actieve `start`.
6. `no_grab = true` als `nu >= einde` of `nu < (15-01 van year)` (tenzij `test_next_season`).
7. `next_uitzondering` = het (gevalideerde) `uitzondering`-veld van `next_year`; ontbreekt dat jaar
   of veld → lege lijst. **[FIX]** Hiervoor wordt **alléén** het `uitzondering`-veld gelezen, niet
   het volledige (mogelijk nog onvolledige) next-year-blok — anders kan een half-ingevuld volgend
   seizoen de selectie van het huidige seizoen breken.

**[NEW] Config-validatie (build faalt bij fout):**
- Alle aanwezige datums zijn geldige kalenderdatums (`30-02` → harde fout, géén stille rollover).
  *De ongeldige legacy-datum wordt **niet** in de productieconfig opgenomen; ze leeft alleen als
  testfixture om de validator te testen.*
- Verplichte velden (zie boven) aanwezig per actief seizoen; ontbreken → harde fout.
- **Invarianten** (`ConfigError` bij schending): `showfrom <= einde`; `reg <= ps <= einde`;
  `ps <= wc,ds,cs,ws <= einde` (gelijke startdag tussen rondes toegestaan); `new < hide`; als
  `newreg` aanwezig is: `new < newreg`. Datumjaren passen bij het seizoensblok.
- Lege strings in `uitzondering` worden verwijderd.

---

## 5. Schemarendering — kernlogica

Per wedstrijd uit het model: `away`/`home`, `date_ams` (`daag`), `date_et` (`old`), `hour_ams`
(`st`/`tm`). `uf` = `date_ams(dm)` + away + home (uitzonderingscode).

### 5.1 Standaardtab (`index.html`) [LEGACY]
`alles` als `nu >= start.ps` (of `nu >= einde`), anders `avond`.
**[NEW]** Ook `alles` zodra het reguliere seizoen voorbij is: `nu >= start.reg` en de
(op §3.2 gefilterde) gameslijst bevat geen wedstrijd meer met `date_ams` vóór de `ps`-datum.
Dit dekt de dagen tussen de laatste reguliere wedstrijd en de eerste postseasondag.

### 5.2 Tijdfilters [LEGACY] (per pagina; regel = behouden wanneer waar)
Op uur `hour_ams`:
- **avond:** toon `14..23`. (legacy: skip `<= 13`)
- **ochtend:** toon `03..06`. (skip `>= 7` of `<= 2`)
- **nacht:** toon `23, 00, 01, 02, 03`. (skip `04..22`)
- **alles:** geen tijdfilter.
- **teampagina:** geen tijdfilter, geen limiet.

**[FIX]** Vergelijkingen numeriek op `hour_ams:int` (legacy deed lexicale stringvergelijking op
zero-padded uren; voor "00".."23" identiek, maar v2 maakt de intentie expliciet).

### 5.3 Overige skip-regels [LEGACY]
- Skip als `date_ams >= start.hide` en geen teampagina.
- Skip als `date_ams > start.new` én `date_et < start.newreg` én `uf` niet in `next_uitzondering`
  (verberg next-season spring training). **[NEW]** Is `newreg` onbekend (None), dan **vervalt deze
  skip volledig** (er wordt niets extra verborgen op die grond).
- Teampagina: skip als noch away noch home == gevraagd team (slug-vergelijking).
- Skip TBD tenzij pagina `alles` of teampagina.
- Toon alleen als away of home in `allowlist_render` (§4.2).
- Toon alleen als `date_ams >= start.showfrom` **of** `uf` in `start.uitzondering` **of** in
  `start[next_year].uitzondering`.
- **[NEW]** Geen wedstrijd wordt meer door een limiet **weggegooid**: álle wedstrijden die de skip-
  regels doorstaan worden gerenderd. De eerste `show_games` (250, telt **gerenderde** rijen) komen
  **inline** in de HTML; de rest gaat naar de tail-JSON voor "meer laden" (§5.9). Dit geldt voor
  overzichts- én teampagina's (laatste hadden voorheen geen limiet; gedrag = identiek omdat alles
  bereikbaar blijft, alleen gefaseerd geladen).

### 5.4 Datumkoppen [LEGACY + FIX]
Eén kop per nieuwe dag. **[FIX]** De legacy-guard `if(daag < $now)` met ongedefinieerde `$now`
zorgde dat de kop altijd toonde; in v2 toont de kop **altijd** (intentie), praktisch identiek
omdat de feed alleen toekomstige wedstrijden bevat.
Prefix: `"vandaag"` / `"morgen"` / NL-weekdag, dan dag + NL-maandnaam.
Speciale labels (op basis van `date_et` = `old`):
- `spring training` als `old < start.reg` en `uf` niet in `uitzondering`.
- ` <next_year>` als `old >= start.new` en `date_ams > start.ps`.
- `opening day` als `old == start.reg`.
- `all-star game` als `old == start.allstargame`.

### 5.5 Teamlogo's [LEGACY, vereenvoudigd]
Logo = `img/<slug>-fs8.png` met optioneel `img/<slug>-dark.png` via `<picture>` (dark-mode).
Slug: lowercase, spatie→`+`; `diamondbacks`/`dbacks`→`d-backs`. Geen logo-bestand → tekstuele
`<span class="logofill">`.
All-star pseudo-teams: `"AL All-Stars"`→`"American League"`, `"NL All-Stars"`→`"National League"`,
getoond met league-logo.
**[FIX/DROP]** De legacy postseason "league-logo-substitutie"-takken waren **onbereikbaar** voor
echte teams (de allowlist-check ving alles af) → in v2 verwijderd. Echte teams tonen altijd hun
eigen logo, óók in postseason. Geen gedragsverschil voor echte wedstrijden.

### 5.6 Postseason-labels [LEGACY, behouden] — gebruikt ESPN-API
Voor rijen met `start.ps <= date_et < start.new`:
1. **ESPN-API-detail** (§3.5) beschikbaar voor `(date_ams, hour_ams, home)` met matchende
   away/home → toon `descr` (bv. "ALCS Game 1\*") en onthoud `event_id` voor de serie-stand.
2. **Anders** fallback uit datum-vensters: bepaal `AL`/`NL` (via teamlijst) en kies het ronde-label
   met een cascade op `date_et` (latere ronde wint). **Exacte condities** (per ronde een
   config-guard t.o.v. `ps` + een datumcheck op `date_et`):
   - **World Series:** `start.ws > start.ps` én `date_et >= start.ws` → `World Series`.
   - **CS:** anders, `start.cs > start.ps` én `date_et >= start.cs` → `<short>CS`.
   - **DS:** anders, `start.ds >= start.ps` én `date_et >= start.ds` → `<short>DS`.
   - **WC:** anders, `start.wc >= start.ps` én `date_et >= start.wc` → `<short> Wild Card`.
   (Let op het verschil: de **config-guard** is `>` voor WS/CS en `>=` voor DS/WC; de
   **datumcheck op `date_et`** is overal `>=`, dus `date_et == ronde-start` valt in die ronde.)
3. **Serie-stand** uit `espnapi/<event_id>.json` (§3.5) → `(x-y)` vanuit away-perspectief.

Voetnoot wanneer postseason-ESPN-data aanwezig: "\* Wordt alleen gespeeld als nodig."

### 5.7 Countdown [LEGACY]
`diff` = dagen tot `start.reg`. Als `diff >= 1` en `nu >= countdown_from`: "Nog **N** dag(en) tot
opening day!". Als `diff == 0`: "Opening day!".

### 5.8 Lege staat [LEGACY]
Geen wedstrijden → "Geen wedstrijden beschikbaar 😢".

### 5.9 "Meer laden" / progressief inladen [NEW]
Doel: schemapagina's tonen niet meteen alle (mogelijk honderden) wedstrijden, maar een beginbatch
met een **"meer laden"**-knop eronder. De renderlogica blijft **volledig server-side** (Python);
"meer laden" laadt alleen extra, **al door de server gerenderde** HTML aan.

- **Splitsing (build-time):** na het toepassen van alle skip-/filterregels (§5.2-5.3) en de
  sortering (§3.1) rendert de build:
  - **inline in de HTML:** de eerste `show_games` (250) rijen, mét hun datumkoppen (§5.4).
  - **`<pagina>.tail.json`:** de resterende rijen als **kant-en-klare HTML-fragmenten**, gegroepeerd
    per "meer laden"-blok van `load_more_batch` (250). Elk blok bevat de rij-HTML **inclusief de
    benodigde datumkop**: begint een blok midden in een dag die al zichtbaar is, dan **geen** dubbele
    kop; begint het op een nieuwe dag, dan **wél** een kop. Zo plakt de client een blok rechtstreeks
    aan zonder render-logica te kennen.
  - JSON-vorm (per pagina): `{ "version": <asset_version>, "page": "<naam>", "total": <int>,
    "batch_size": 250, "blocks": ["<html-fragment-blok-1>", "<html-fragment-blok-2>", ...] }`.
- **Knop:** staat alleen onder een pagina met een niet-lege tail. Tekst "meer laden"; toont eventueel
  "(nog N)". Na het laden van het laatste blok verdwijnt de knop.
- **Client (§6.6):** klik → volgende blok uit de tail-JSON ophalen (of uit een al geladen, in-memory
  lijst), als HTML **aanplakken** onder de laatste rij, dan `applyFavoriteHighlights(root)` opnieuw
  draaien op de nieuwe rijen.
- **Escaping/HTML-kwaliteit:** de fragmenten zijn server-gerenderd met dezelfde autoescape/HTML5-eis
  als de inline rijen (§2). De client zet ze met `innerHTML` op de pagina; er komt **geen**
  onbetrouwbare/externe tekst rechtstreeks in de DOM buiten deze server-gerenderde fragmenten om.
- **Graceful degradation:** zonder JavaScript is alleen de inline beginbatch zichtbaar (geldige,
  bruikbare pagina). Is de tail-JSON (nog) niet beschikbaar (offline, eerste klik zonder netwerk),
  dan blijft de beginbatch staan en meldt de knop dat meer laden nu niet lukt; de pagina crasht niet.

---

## 6. Client-side gedrag

### 6.1 Favorieten [LEGACY, gemoderniseerd]
- localStorage-key `honkbal-favorite-teams` (JSON-array genormaliseerde namen).
- Normalisatie: trim, lowercase, `+`→spatie; `diamondbacks`/`dbacks`→`d-backs`.
- API (gedeeld module): `getFavorites`, `setFavorites`, `isFavoriteMatchup(away,home)`,
  `applyFavoriteHighlights(root)`. Rijen met `data-away-team`/`data-home-team` → class
  `favorite-game`. Herapplicatie op load en op `storage`-event (cross-tab).
- **[NEW]** Frontend als ES-module(s), geen inline `<script>`-blobs; gedrag identiek.

### 6.2 Scorepagina [LEGACY, met FIX]
- Endpoint: `https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=linescore,team&date=<MM/DD/YYYY>`.
- 5-daags venster terugkijkend in `America/New_York`. localStorage `scores-<YYYYMMDD>` +
  `scores-meta-<YYYYMMDD>` (`{cachedAt, version}`). **`CACHE_VERSION` ophogen bij shape-wijziging.**
- Filter `abstractGameState` ∈ {Live, Final, Preview(delayed/warmup)}. Splits live/finished.
  - Live: favoriet eerst, dan `inning*2 + (Top?0:1)`.
  - **[FIX]** Finished: favoriet eerst, dan `gameDate` **oplopend (vroegste eerst)** — de
    eerdere spec-tekst "vroegste laatst" was fout; de code is oplopend. v2 = vroegste eerst.
- Statuslabels: `warmup`, `DEL` (+inning/pijl), live (inning + pijl + honken-SVG + outs-SVG), `final`.
- Logo-slug + dark-mode als §5.5. Auto-refresh 30 s bij live, anders 300 s; alleen datums met
  live/delayed/warmup worden snel ververst. Tijdweergave Amsterdam (HH:mm).
- **[NEW] Cache-contract (één regel, niet tegenstrijdig):** een cache-entry blijft bruikbaar zolang
  z'n datum binnen het venster valt én de shapeversie klopt — **geen harde TTL-cap** (alleen
  datumcleanup: laatste 7 dagen + opgevraagde dagen). Bij netwerkfout val je terug op cache en toon
  je de **leeftijd** ("offline — laatst bijgewerkt om HH:mm"). De getoonde "laatste update" =
  het **nieuwste succesvolle fetch-moment** over de getoonde dagen (max van de per-dag `cachedAt`);
  komt alles uit cache, dan de nieuwste `cachedAt` uit cache (niet het moment van de mislukte poging).

### 6.3 Standenpagina [LEGACY, volledig uitgeschreven]
- Endpoint: `https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&standingsTypes=regularSeason&hydrate=team&season=<YYYY>`.
- **[FIX]** `season` = het **actieve seizoen** (§4.3), server-side geïnjecteerd, niet
  `new Date().getFullYear()` uit de browser (dat brak in de offseason).
- localStorage `standings-<season>` + `standings-meta-<season>` (`{cachedAt, version}`),
  `standings-tab`. Max-age/refresh 300 s; `init()` rendert cache en ververst altijd.
  **[FIX]** Elke gevalideerde succes-respons wordt **atomair** opgeslagen (legacy schreef niet weg
  zolang de oude metadata nog "vers" was → onbetrouwbare laatste-succestijd).
- Divisie-IDs: AL 201/202/200, NL 204/205/203. Leagues 103=AL, 104=NL.
- Tabs + **volledige sorteringen** (normatief):
  - **division:** per divisie; sorteer op `divisionRank` ↑, dan `winningPercentage` ↓.
  - **al / nl:** per league; `leagueRank` ↑, dan `winningPercentage` ↓, dan `wins` ↓.
  - **mlb:** alle teams; `winningPercentage` ↓, dan `wins` ↓.
  - **wildcard:** per league, alleen `wildCardRank` 1..6; sorteer `wildCardRank` ↑. Houders
    (`wildCardGamesBack` begint met `+`) → groene rij. Kolomkop "WC GB".
- Kolommen: Team (+logo), W, L, PCT, GB/"WC GB" (`-`→`—`), L10 (`splitRecords.lastTen`), Streak
  (`streakCode`). Favorieten → `favorite-game`.
- **[NEW] Verplichte velden per view** (rij die ze mist → overslaan, niet crashen; lege sectie →
  nette melding): alle views vereisen `team`, `wins`, `losses`, `winningPercentage`. Daarnaast:
  *division* vereist `divisionId` + `divisionRank`; *al/nl* vereist `leagueRank`; *wildcard* vereist
  `wildCardRank` (1..6) + `wildCardGamesBack`; *mlb* vereist geen rank. Onbekende `divisionId` →
  sectie overslaan.
- **[NEW]** Favorietenwijziging in andere tab herrendert ook standings (storage-handler dekt
  standings-rijen, niet alleen matchup-rijen).

### 6.4 Settings [LEGACY, gemoderniseerd]
Checkbox-grid met alle teams. Sync met favorieten-module; opslaan → statusmelding (2,5 s); wissen
→ alles uit + opslaan; cross-tab via `storage`. Daarnaast de tv-gids-opties (§6.11) en de
bètafeature-checkboxes (§6.9), beide direct opgeslagen.

### 6.5 Service worker [LEGACY, expliciet contract]
- Cacheversie-naam ophogen bij wijziging pre-cache of strategie.
- **PRECACHE:** root, `offline.html`, favicon, icon, alle hoofdpagina's + 30 teampagina's.
  **[NEW]** Documenteer expliciet dat CSS/manifest/teamlogo's én de **`*.tail.json`-bestanden**
  *niet* in precache zitten (worden lazy gecachet) — "offline beschikbaar" betekent dus niet "alle
  assets/extra games vooraf aanwezig".
- Strategie: **HTML/documenten** network-first → cache → `offline.html`; **stylesheets**
  network-first (snelle publicaties); **`*.tail.json`** network-first → cache (zodat "meer laden" na
  één online bezoek ook offline werkt); **images/fonts** cache-first. Registratie
  `updateViaCache:'none'`.
- **[BESLISSING vastgelegd]** Publieke paden zijn **root-relatief** (`/avond.html`, `/img/...`).
  Service-worker-scope = `/`.

### 6.6 "Meer laden" (schema) [NEW]
Gedeelde ES-module die op schemapagina's de "meer laden"-knop bedient (zie §5.9):
- Bij eerste klik: `fetch('<pagina>.tail.json')` (network-first; daarna uit SW-cache). Bewaar de
  `blocks` in-memory zodat vervolgkliks geen nieuwe fetch nodig hebben.
- Per klik: het volgende `blocks`-fragment als HTML **onder de laatste rij** plakken
  (`insertAdjacentHTML`), daarna `applyFavoriteHighlights(root)` op de nieuw toegevoegde rijen
  (favorieten-highlight ook op bijgeladen wedstrijden, incl. cross-tab `storage`-event).
- Versie-check: gebruik alleen een tail-JSON waarvan `version` bij de pagina past; mismatcht die
  (oude SW-cache), negeer en haal opnieuw van netwerk.
- Knop verbergen zodra alle blokken geplakt zijn. Faalt de fetch (offline, nog niet gecachet): knop
  blijft staan met een korte melding ("meer laden lukt nu niet — offline"); de pagina blijft intact.

### 6.7 Debug-pagina [NEW contract]
Na het droppen van de tv-gids/tvgids-bronnen toont `debug.html` (genereerd build-time):
buildversie + buildtijd; schedule `modified`/`refreshed`; actief seizoen + `next_year` + `no_grab`;
de ESPN-postseason-bron (alleen `fetched_at` + aantal events, of "niet actief buiten postseason");
en het bestaan/timestamp van de gegenereerde `docs/`-hoofdbestanden. **Geen** verwijzingen meer naar
`espn.json`, `tvgidsnl.json` of oude scorebestanden.

### 6.8 Live-sectie ("nu") op de avond-tab [NEW]
De avond-tab toont bovenaan een client-side live-sectie met de wedstrijden die op dít moment
bezig zijn, inclusief scores, en hernoemt het navigatielabel van de avond-tab client-side naar
**"nu + avond"**. De sectie staat voor **iedereen** aan (geen opt-in; was tot juli 2026 de
bètafeature `live`, §6.9). Server-side blijft het label "avond": zonder JS draait de module niet
en is er ook geen live-sectie. Alleen de tab in de schedule-subnav (`.nav-pills`) wordt hernoemd;
de topnavigatielink "schema" (→ `/`) behoudt zijn label:
- Op pagina's met `page == 'avond'` én altijd op `index.html`, ongeacht de default-tab (§5.1): ook
  na het reguliere seizoen en in de postseason, als de voorpagina `alles` toont.
- ES-module `live.js` + entry `live-entry.js` (zelfde patroon als §6.1/§6.2: geen inline blobs).
- Endpoint als §6.2 (MLB Stats API, `hydrate=linescore,team`), maar met een venster van **2 dagen**
  (NY-vandaag + NY-gisteren): een wedstrijd die in de Nederlandse ochtend nog loopt hoort bij de
  NY-kalenderdag van gisteren.
- Toont wedstrijden met `classifyGame` ∈ {live, preview} (bezig, warmup of delayed) met dezelfde
  rij-markup en statuslabels als de scorepagina; `finished` wordt hier **niet** getoond (daarvoor
  is de scorepagina). Sortering over de gezamenlijke set: **favoriet eerst**, daarbinnen live vóór
  preview, daarbinnen vergevorderde inning eerst (live) / vroegste `gameDate` eerst (preview).
- Kop "nu bezig". Geen live wedstrijden → sectie volledig leeg/verborgen (geen lege tabel of
  melding). De sectie sluit zonder losse tussenruimte aan op het schema eronder (net als de
  overgang tussen twee schemadagen); geen extra `margin` tussen de live-tabel en het schema.
- Dedup met het statische schema: voor elke getoonde live wedstrijd wordt alleen een statische rij
  verborgen als `data-away-team`/`data-home-team` overeenkomen én `data-start` maximaal **60
  minuten** afwijkt van de `gameDate` van de API. Bij elke refresh wordt de verborgen set opnieuw
  bepaald (een afgelopen wedstrijd verdwijnt uit de live-sectie en de statische rij komt terug).
  Bij meerdere geldige kandidaat-rijen (doubleheader) wint de rij met de kleinste tijdsafstand.
  Ontbreekt een leesbare starttijd aan een van beide kanten of valt geen kandidaat binnen de grens,
  dan wordt geen statische rij verborgen; een eventuele dubbele weergave is veiliger dan een andere
  wedstrijd uit het schema verbergen.
- Dagkoppen waarvan alle rijen verborgen zijn (naar de "nu bezig"-sectie verplaatst) worden mee
  verborgen — anders blijft er een verweesd datumkopje staan. Dezelfde kop-synchronisatie als het
  interessefilter (§6.9): een rij telt als zichtbaar zolang hij niet door de live-dedup (`hidden`)
  én niet door het filter (`interest-hidden`) verborgen is.
- Auto-refresh: 30 s zolang er live/preview-wedstrijden zijn, anders 300 s (zelfde regel als §6.2).
  Netwerkfout → sectie ongewijzigd laten (geen foutmelding; het statische schema blijft leidend).
  Geen localStorage-cache: de sectie is per definitie "nu".
- **Poll-vensters:** de API wordt alleen aangeroepen als er live games verwácht worden. Build-time
  krijgt `#live-container` een `data-live-windows`-attribuut: JSON-array van starttijden
  (epoch-seconden) over de **volledige** gameslijst (nachtgames staan niet op de avond-pagina maar
  zijn 's ochtends juist live), van `LIVE_WINDOW_HOURS` (5) terug tot `LIVE_POLL_HORIZON_HOURS`
  (48) vooruit; TBD-games leveren geen venster. **Bij het laden pollt de module altijd één keer**,
  ongeacht de vensters: een wedstrijd die nú bezig is moet direct verschijnen, óók als het
  build-time venster hem mist (game die al >5u loopt door delay/extra innings, of een verouderde
  `data-live-windows`). Daarna pollt de module alleen binnen `[start, start + 5u]` van enig venster;
  daarbuiten wacht hij (timer tot de eerstvolgende start) of stopt hij als er geen venster meer over
  is. **Status wint van het venster:** zag de laatste
  fetch nog live/preview-games, dan blijft de module pollen tot de API ze klaar meldt (uitlopers
  > 5u). Attribuut afwezig/onleesbaar → altijd pollen (fallback = gedrag zonder gating).

### 6.9 Bètafeatures + interessefilter [NEW]
Experimentele features zijn **opt-in** via een "Bètafeatures"-sectie op de instellingenpagina:
- Opslag: localStorage-key `honkbal-beta-features` (JSON-array van feature-namen), browser-lokaal
  zoals favorieten (§6.1). Checkbox-wijzigingen worden **direct** opgeslagen (geen opslaan-knop);
  onbekende namen in de payload worden genegeerd. Bèta-checkboxes dragen `name="beta"` en vallen
  buiten de favorieten-flow (opslaan/wissen raakt ze niet).
- Entry-modules van bètafeatures checken de flag vóór init; met de flag uit gedraagt de site zich
  exact als zonder de feature.
- Bekende features: **`interest`** (hieronder). Een feature die uit bèta gaat wordt uit
  `BETA_FEATURES` én van de instellingenpagina verwijderd; de naam telt dan als onbekend en
  verdwijnt vanzelf uit bestaande localStorage-payloads (zo was `live`, §6.8, tot juli 2026 bèta).

**Interessefilter (`interest`):** slider op alle schemapagina's die alleen de interessantste
wedstrijden toont, op basis van het build-time enrichment-percentiel (§11.2 punt 3):
- Rendering: elke schema-rij met enrichment draagt `data-interest="<percentiel 0..100>"`; rijen
  zonder enrichment (postseason, all-star) hebben het attribuut niet en vallen **buiten het
  filter** (blijven altijd zichtbaar).
- ES-module `interest.js` + entry `interest-entry.js`. De module injecteert de slider (bereik
  0..95, stap 5) boven de schematabel; drempel 0 = filter uit. De badge toont "top X%"
  (X = 100 − drempel). Draagt geen enkele rij `data-interest` (postseason-fase, §11.1), dan wordt
  de slider **niet geïnjecteerd** — anders zou elke drempel de hele pagina leegfilteren.
- Rijen met percentiel < drempel krijgen class `interest-hidden` (CSS `display:none`) — bewust een
  eigen klasse en niet `hidden`, zodat het filter nooit conflicteert met de rij-dedup van de
  live-sectie (§6.8). Dagkoppen waarvan alle rijen verborgen zijn worden mee verborgen (gedeelde
  kop-synchronisatie met §6.8, die zowel `interest-hidden` als de live-`hidden` meetelt).
- De drempel wordt bewaard in localStorage (`honkbal-interest-threshold`) en bij "meer laden"
  (§6.6) opnieuw toegepast op bijgeladen rijen (MutationObserver).

### 6.10 Veroudering van het statische schema [NEW]
Het schemafilter van §3.2 is build-time en dus een momentopname, terwijl de pagina daarna uren
blijft staan: tussen de nachtbuild (01:00) en de ochtendbuild (10:00) zit een gat van negen uur
(§8). Een pagina die om 01:00 gebouwd is bevat dus nog de wedstrijden van gisteravond die om
01:00 net binnen het grace-window vielen (bv. 21:45 en 22:10), en die stonden er 's ochtends om
05:55 nog steeds — allebei al uren afgelopen. De browser past daarom hetzelfde filter opnieuw toe:
- ES-module `stale.js` + entry `stale-entry.js` op **elke** schemapagina (ook team-pagina's, ook
  zonder live-sectie). Geen opt-in, geen bèta.
- Zelfde grens en zelfde tweedeling als §3.2, met `GRACE_MS` in `stale.js` gelijk aan
  `LIVE_GRACE_HOURS` in `config/toggles.py`: getimede rijen verouderen moment-nauwkeurig op
  `data-start` (`nu >= start + grace`), rijen zonder starttijd (TBD) datum-granulair op de
  `data-date` van hun dagblok (`<tbody data-date="YYYY-MM-DD">`, Amsterdamse kalenderdatum) —
  pas verbergen als die dag zelf voorbij is.
- Verouderde rijen krijgen class `stale-hidden` (CSS `display:none`) — bewust een eigen klasse,
  net als `interest-hidden` (§6.9), zodat de veroudering nooit vecht met de rij-dedup van de
  live-sectie (`hidden`, §6.8). Onleesbare `data-start` of een dagblok zonder `data-date` →
  **niet** verbergen (het statische schema blijft leidend).
- Dagkoppen zonder zichtbare rijen worden mee verborgen via dezelfde kop-synchronisatie als
  §6.8/§6.9; die telt nu `hidden`, `interest-hidden`, `stale-hidden`, `final-hidden` én
  `series-decided` (§6.12) mee.
- Opnieuw wegen: bij het laden, bij "meer laden" (§6.6, MutationObserver) en elke 60 s, zodat een
  openstaande pagina een wedstrijd die over de grens gaat zonder reload laat verdwijnen.
- **Status-check binnen het grace-window**: een wedstrijd die al afgelopen is maar nog binnen
  start + grace valt (bv. start 02:00, klaar 05:00, grens 06:00) hoort niet meer in het schema —
  de live-sectie (§6.8) zet zijn statische rij na afloop juist terug. Zijn er getimede rijen met
  `start <= nu < start + grace`, dan doet `stale.js` één MLB-Stats-API-call
  (`/schedule?sportId=1&startDate..endDate` over de NY-dagen van die rijen) en geeft rijen waarvan
  de best passende game (zelfde teampaar, `gameDate` binnen 60 min; doubleheader: dichtstbij)
  `abstractGameState == "Final"` heeft class `final-hidden`. Bij het laden en elke 5 min zolang
  zulke rijen bestaan; geen zulke rijen → geen call; netwerkfout → niets wijzigen.
- Een wedstrijd die ná het grace-window nog loopt (delay/extra innings) verdwijnt uit het
  statische schema maar blijft op de avond-tab zichtbaar in de live-sectie (§6.8), die op status
  in plaats van op starttijd werkt. Zonder JS gebeurt er niets en blijft de build-time output
  staan (§9).

### 6.11 Tv-gids-instellingen [NEW]
De zenderlogo's (§3.3) staan voor iedereen aan; twee gewone instellingen (geen bèta) op
`/settings.html` regelen de zichtbaarheid client-side (het schema is statische HTML):
- **Zenderlogo's aan/uit** — `localStorage`-key `honkbal-espn-logos`; afwezig of `"1"` = aan,
  `"0"` = uit. Default (geen entry) = **aan**.
- **Alleen bij Nederlands commentaar** — key `honkbal-espn-nl-only`; afwezig of `"0"` = uit,
  `"1"` = aan. Default = **uit**.
- ES-module `espn.js` + entry `espn-entry.js` op elke schemapagina zet body-klassen: `espn-off`
  (verbergt alle `div.espn`) en `espn-nl-only` (verbergt `div.espn` zonder `data-nlcom`). Door de
  body-klasse-aanpak gelden de regels automatisch ook voor tail-rijen van "meer laden" (§6.6) —
  geen per-rij JS of MutationObserver.
- Checkboxes op de instellingenpagina dragen `name="tv"` (values `logos`/`nlonly`) en worden
  direct opgeslagen (patroon §6.9); cross-tab sync via `storage`-events. Zonder JS of zonder
  opgeslagen keuze toont het schema gewoon alle logo's uit de build.

### 6.12 Postseason-serie-badge en -stand (client-side) [NEW]
Postseason-wedstrijden tonen client-side hun serie-label en de actuele serie-stand, bron MLB
Stats API (`/schedule`, gewone `hydrate=linescore,team`-payload; geen extra hydrate):
- **Label** uit `gameType` (`F`=WC, `D`=DS, `L`=CS, `W`=World Series) + liga (`team.league.id`
  103=AL/104=NL, fallback `seriesDescription`) + `seriesGameNumber`, `*` bij `ifNecessary == "Y"`:
  `NLWC - Game 3`, `ALDS - Game 5*`, `World Series - Game 1` — zelfde vorm als de ESPN-labels (§5.6).
- **Stand** `(x-y)` = `teams.away.leagueRecord.wins`-`teams.home.leagueRecord.wins` (in de
  postseason telt `leagueRecord` alleen de huidige serie); uitteam vooraan. `0-0` → geen stand.
- **Live-/scorerij** (§6.2/§6.8): badge `<span class="stp">label (x-y)</span>` in een
  `div.series-line` boven het uitteam; de rij krijgt class `ps-score-row`.
- **Statisch schema**: ES-module `series.js` + entry `series-entry.js` op elke schemapagina.
  Zonder `tr.ps-row` geen API-call. Anders één call
  (`gameType=F,D,L,W&startDate..endDate` over de `data-start` van de postseason-rijen ±2 dagen);
  per rij de API-game van hetzelfde teampaar met de dichtstbijzijnde `gameDate` (max. 48 u). Valt
  die binnen 60 min, dan vervangt het API-label het build-label; anders (bv. een `*`-game van een
  al beslist serie) blijft het build-label staan. De stand vervangt een eventuele build-time stand.
  Netwerkfout of geen match → badge ongewijzigd.
- **Beslist serie**: heeft een rij geen eigen API-game (geen match binnen 60 min), valt de
  gevonden game vóór de rij én is de serie daarin beslist (één team > `gamesInSeries`/2 zeges:
  WC 2, DS 3, CS/WS 4), dan wordt de rij niet meer gespeeld en krijgt hij class `series-decided`
  (verborgen; telt mee in de dagkop-synchronisatie van §6.8/§6.9/§6.10). Netwerkfout of onbekend
  `gamesInSeries` → rij blijft staan.

---

## 7. Assets en cache-busting
- **[BESLISSING vastgelegd]** Eén strategie: **alle assets root-relatief** (`/css/...`, `/img/...`)
  met `?<asset_version>` cache-buster, voor zowel server-gerenderde HTML als de scores/standings-JS.
- `asset_version` = inhoud van `version.txt` (door CI gezet als `<sha:12>-<run>`), fallback
  `mtime(style.css)`; als `?<version>` cache-buster.

---

## 8. CI-build en publicatie [NEW]
- **Build-workflow (volledig):** uv-omgeving → data fetchen (MLB schedule; in postseason ESPN-API)
  → `version.txt` schrijven → site renderen naar `docs/` → statics kopiëren → publicatie-artifact.
- **Rebuild-workflow (zonder fetch):** hergebruik gecachte data; render opnieuw.
- **[NEW] Robuustheid:** data-cache wordt zowel opgeslagen als hersteld; ontbrekende cache faalt
  niet stil maar logt duidelijk.
- **[NEW] CI-validatie:** config-datumvalidatie (§4.3) en de acceptatietests (§12) draaien als
  gate vóór publicatie.
- **[NEW] Hosting:** Vercel, als kant-en-klare statische output (Build Output API v3, geen build
  op Vercel). Routes/headers in `deploy/vercel/config.json`: onbekende paden → `404.html`
  (status 404), `/js/v/*` krijgt `cache-control: public, max-age=31536000, immutable` (URL is
  per `asset_version` uniek, §7); overige bestanden houden de Vercel-default (revalideren).
  Deploy-secrets (`VERCEL_TOKEN`/`VERCEL_ORG_ID`/`VERCEL_PROJECT_ID`) staan alleen in de
  GitHub-environment `production`; ontbreken ze, dan faalt de deploy luid.
- **[NEW] CDN-purge:** honkbal.net draait achter een bunny.net-pull-zone vóór Vercel; na
  elke geslaagde deploy (build- én rebuild-workflow) purget CI de hele pull zone via de
  bunny-API (secrets `BUNNY_API_KEY`/`BUNNY_PULLZONE_ID`). Faalt zacht: ontbrekende secrets of
  een mislukte purge geven een waarschuwing, de cache verloopt dan volgens TTL.

---

## 9. Graceful degradation [NEW]
- **Geen/oude MLB-scheduledata:** schema rendert lege staat (§5.8); build faalt niet.
- **Geen ESPN-API-data in postseason:** val terug op date-derived ronde-labels (§5.6 stap 2);
  geen serie-stand.
- **MLB Stats API onbereikbaar (client):** scores/standen tonen cache + offline-melding.
- **Tv-gids-bronnen onbereikbaar:** bestaande `tv_guide.json` blijft (soft-fail §3.3); zonder
  bruikbare cache rendert het schema zonder zenderlogo's. Alleen tvgids.nl beschikbaar → minder
  matches (geen teamnamen op de meeste dagen, geen NL-badges); de eerstvolgende build probeert
  dan automatisch een verse apiKey af te kijken (§3.3, zelfherstel).
- **Tail-JSON onbereikbaar (client):** "meer laden" meldt dat het offline niet lukt; de inline
  beginbatch blijft staan (§5.9).
- **Geen JS (of `stale.js` niet geladen):** het schema toont de build-time selectie (§3.2); rijen
  van afgelopen wedstrijden verouderen dan niet mee (§6.10) tot de volgende build.

---

## 10. Jaarlijks onderhoud
Nieuw `start[YYYY]`-blok (alle verplichte datums + uitzonderingen). Config-validatie (§4.3) vangt
ontbrekende/ongeldige velden. Controleer standaardtab, datumkoppen, `debug.html`.
Tv-gids (§3.3): de ESPN watch-apiKey herstelt zichzelf (discovery in `build.yml`; handmatig:
`npm run discover:espn`). Controleer alleen nog de tvgids.nl-kanaal-id's — en de discovery
zelf — zodra de fetch structureel op de fallback of op niets draait.

---

## 11. Uitgelichte wedstrijden: regelgebaseerde interessantheid [NEW]
`Game.enrichment` is een optioneel veld (`{score: float, label: str, reasons: tuple[str]}`) dat
een aparte build-stap (`honkbal/enrichment.py`) vult met een **regelgebaseerde** interessantheids-
score. Het was oorspronkelijk een lege toekomsthaak; vanaf de "uitgelicht-berekening" is het
geïmplementeerd (geen AI/ML — deterministische regels op publieke signalen).

### 11.1 Pijplijn
1. **Fetch** (alleen vóór `season.windows.ps`): `honkbal/fetch/standings.py` haalt de MLB-StatsAPI-
   standen op en cachet genormaliseerd naar `.data/standings.json`. `honkbal/fetch/playoff_odds.py`
   leest optioneel `.data/playoff_odds.json` (genormaliseerde playoff-kansen; bron-scraper zie §11.4).
2. **Score** (`enrich_games` → `score_game`): elke reguliere-seizoenwedstrijd krijgt een score 0..100.
   Postseason wordt **overgeslagen** (`clock.now() >= season.windows.ps`) — daar zijn al expliciete
   fase-labels en is elke wedstrijd inherent belangrijk.
3. **Percentiel**: na het scoren krijgt elke gescoorde game een percentiel 0..100 binnen de
   gescoorde games van deze build (`Enrichment.percentile`). Het interessefilter (§6.9) werkt op
   percentielen, niet op ruwe scores: de ruwe verdeling is samengeperst (~20..60 in de praktijk)
   en verschuift met de seizoensfase en signaalbeschikbaarheid; "drempel 75" betekent op
   percentielen altijd "toon de top 25%".
4. **Context**: `render/context.py` exposeert `enrichment_score/label/reasons/percentile` op
   `RowContext`.

### 11.2 Signalen (opgeteld, geclampt 0..100; élke reguliere-seizoenwedstrijd krijgt een score)
- **Rivalry** (`config/rivalries.py`, tier 1..3) → `tier × 8`.
- **Zelfde league** (+4) / **zelfde divisie** (+6, `config/teams.py::TEAM_DIVISIONS`).
- **Teamkwaliteit** (winning %): hoge én gelijkwaardige teams scoren hoger (cap 18).
- **Standings-druk** (cap 24): het **gemiddelde** van de racedruk per team × 18 — een race-team
  tegen een kansloos team is half zo interessant als twee race-teams. Racedruk per team: kleinste
  van divisie-/wildcard-achterstand ≤ 8 games, lineair aflopend; voor een **divisieleider** telt
  de achterstand van de nummer 2 in zijn divisie (games_back 0 van de leider zelf is geen druk).
  Reden `playoffrace` pas vanaf gemiddelde druk ≥ 0.5. Plus beide top-3 in dezelfde divisie (+6,
  `divisiedruk`).
- **Playoff-odds-spanning**: kans dicht bij 50% en gelijke kansen tussen beide teams (cap 30).
- **Context-bonus**: weekend (+3), gunstige tijd 19–22u AMS (+3). **TBD** −6.

Labels (alleen vanaf de uitlicht-drempel, score ≥ 18; daaronder `label = None`):
`topwedstrijd` (score ≥ 55) · `rivalry` · `playoffrace` · anders `uitgelicht`.

### 11.3 Robuustheid
Standings-fetch faalt **zacht** (waarschuwing; valt terug op bestaande cache of basisregels) en
blokkeert de build nooit. Ontbreken standen/odds, dan dragen alleen de beschikbare signalen bij.
Acceptatie: het wedstrijdmodel en de renderfunctie accepteren een gevulde `enrichment` zonder de
overige rendering te veranderen (tonen als badge/sorteersleutel volgt later).

### 11.4 Playoff-odds-bronnen — genormaliseerd contract
De stabiele grens is het **genormaliseerde** bestand `.data/playoff_odds.json`:
`{"source": "fangraphs"|"baseball-reference", "teams": [{"team": <slug>, "make_playoffs": 0..1, "win_division": 0..1, "win_world_series": 0..1}]}`.
`load_playoff_odds` leest uitsluitend dit formaat; bron-adapters zetten ruwe data om. De primaire
bron is FanGraphs playoff-odds
(`https://www.fangraphs.com/api/playoff-odds/odds?projmode=combo&standingsType=div&season=<jaar>&dateDelta=`,
JSON per team). Als FanGraphs faalt door HTTP-blokkade, lege payload of gewijzigd schema, valt de
fetcher terug op Baseball-Reference
(`https://www.baseball-reference.com/leagues/majors/<jaar>-playoff-odds.shtml`, HTML-tabel).

Live gevalideerd op 2026-06-24:

- FanGraphs publieke odds-kolommen: team-identiteit `TeamName`, playoff-kans `MakePlayoffs`,
  divisietitel `WinDiv`, World Series `WinWS`.
- Baseball-Reference publieke odds-kolommen: team-identiteit `Team`, playoff-kans `Make Playoffs`
  (of afleidbaar uit `Division Winner` + `Wild Card`), divisietitel `Division Winner`,
  World Series `World Series`.

Beide adapters falen zacht: alleen een niet-lege, gevalideerde teamset schrijft
`.data/playoff_odds.json`; anders blijft de bestaande cache intact en draait enrichment zonder nieuw
odds-signaal.

---

## 12. Acceptatiecriteria & golden fixtures [NEW, verplicht]
Vaste fixtures + verwachte uitkomsten voor minimaal:
1. Tijdzoneconversie NY→Amsterdam op normale dagen **en** beide DST-overgangen.
2. Wedstrijden die door de tz-conversie van kalenderdatum wisselen (`date_et` ≠ `date_ams`).
3. Alle filtergrenzen per pagina: uren 02, 03, 04, 06, 07, 13, 14, 22, 23 én `TBD`.
4. De inline beginbatch (**exact 250** rijen in de HTML) en stabiele volgorde binnen één dag
   (`time_ams`, TBD achteraan); bij >250 gerenderde wedstrijden komt de rest in `<pagina>.tail.json`
   en gaat **geen** wedstrijd verloren (§5.9).
5. `showfrom`, `hide`, `new`, `newreg`, `uitzondering` en de jaarovergang (actief-seizoen-algoritme).
6. Postseason: alle fasegrenzen (`wc/ds/cs/ws`), ESPN-API-match vs. fallback-label, serie-stand-
   parsing ("Series tied …" en "… lead(s) series …"), en onbekende summary-tekst (geen crash).
7. Scores (client, met mock-respons): Live, Preview/warmup, delayed, Final, favorietensortering,
   cache-fallback en lege API-respons.
8. Standings (client, met mock-respons): alle vijf views, volledige tie-breakers, offseason-seizoen,
   cache-fallback, ontbrekende velden.
9. Service worker: installatie vanaf lege cache, update van HTML/CSS, offline-fallback.
10. Config-validatie: ongeldige datum (`30-02`), ontbrekend verplicht veld én geschonden invariant
    (bv. `ps > einde`) → build-fout; `newreg` afwezig (None) → geen fout, skip §5.3 vervalt.
11. Een schone CI-build zonder vooraf bestaande Actions-cache produceert alle `docs/`-bestanden.
12. Gedeeltelijke fetch: als requests onder de minimumdrempel falen blijft de last-known-good-cache
    intact (geen lege/partiële overschrijving); `modified=refreshed` als geen `Last-Modified`.
13. TBD-doubleheader (twee wedstrijden, zelfde teams/dag, beide TBD) → beide blijven behouden.
14. "Meer laden" (§5.9): bij >250 gerenderde wedstrijden bevat de HTML exact de eerste 250 en de
    `<pagina>.tail.json` de rest als HTML-blokken; een blok dat een nieuwe dag begint krijgt een kop,
    een blok dat een lopende dag voortzet niet; client plakt blokken aan in volgorde, herhighlight
    favorieten op bijgeladen rijen, en de knop verdwijnt na het laatste blok. Tail-JSON onbereikbaar
    → nette melding, beginbatch blijft (geen crash).
15. Feed-ontdekking (§3.2): de diagnostische run over range 105..161 wijst per `team_id` correct aan
    welke een geldig MLB-teamfeed leveren (inclusief de all-star-pseudo-feed) en welke alleen
    affiliate-/lege feeds; de afgeleide mapping dekt precies de 30 MLB-teams + all-star.
16. Tv-gids (§3.3, met gepinde fixtures voor beide bronnen): adapter-parsing (kanaal-/team-
    normalisatie, UTC→Amsterdam, beide tvgids-payloadvormen), de NL-commentaar-detectiematrix
    (incl. negatief "NL All-Stars"), magazinefilter, ESPN-totaalfalen → tvgids-fallback,
    beide-falen → cache intact, carry-over; matching (ongeordende teamset, tolerantiegrens,
    doubleheader-dichtstbij, teamloos-precies-één vs. ambiguïteit, TBD/replay nooit); render
    (gematchte rij → `div.espn` + dark-`<source>` + `?<asset_version>`, NL-badge aan/afwezig,
    geen div zonder match); client-instellingen (§6.11: defaults zonder localStorage,
    body-klasse-waarheidstabel, cross-tab sync, direct opslaan).

Vergelijking via semantische snapshots (genormaliseerd model + DOM-fragmenten), niet volledige
HTML-bytes.

---

## 13. Beveiliging / hygiëne [NEW]
- De repository is publiek: code, documentatie, workflows, tests, fixtures en snapshots moeten
  openbaar publiceerbaar zijn.
- Geen secrets, tokens, accountconfig, lokale instellingen, persoonlijke data of onnodige
  operationele infrastructuurdetails in repo, fixtures of gegenereerde output.
- Secret-waarden staan alleen in het secretbeheer van het CI-platform. Documentatie gebruikt
  placeholders of generieke namen.
- Fixtures en snapshots bevatten alleen publieke, minimale testdata; strip headers, metadata en
  ruwe payloads die niet nodig zijn voor de test.
- Gegenereerde en lokale artefacten blijven buiten Git: `docs/`, `version.txt`, `.data/`,
  `.claude/settings.local.json`, dependency-mappen, caches en test-output.
- Vóór publicatie of na imports/history-wijzigingen: scan de te publiceren Git-history op gevoelige
  waarden.
