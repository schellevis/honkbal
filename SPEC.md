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

**Uit scope / [DROP]:**
- **ESPN-tv-uitzendgids** (`gids-grab`, `gids-read`, `espn.json`, `simple_html_dom`): de
  "welk kanaal zendt uit"-indicatoren en de `espn/`-kanaallogo's (ESPN 1/2/3) op het schema.
- **tvgids.nl-tak** (`tvgidsnl.php`, `tvgidsnl.json`): in legacy al volledig dode code.
- Backend-/publicatiescripts en externe-serviceconfig buiten deze generator.

**Toekomstig (niet in deze herbouw, [NEW]-haak):** AI-inschatting van "interessantheid" per
wedstrijd. Het genormaliseerde wedstrijdmodel (§3.1) krijgt een expliciet optioneel
verrijkingsveld zodat dit later als losse build-stap kan worden ingeplugd (zie §11).

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

Topnavigatie: **schema** → `avond.html`, **scores** → `scores.html`, **standen** →
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
  enrichment:  Enrichment | None   # [NEW] haak voor toekomstige AI-score; standaard None
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
- **Filter:** alleen wedstrijden met start `> nu` (strikt vanaf nu; reeds begonnen wedstrijden
  vervallen). **[FIX — was `> (nu − 1 dag)` in legacy; v2 toont strikt toekomstige wedstrijden]**
  Getimede regels: moment-nauwkeurig (`start > nu`). TBD-regels (geen starttijd): datum-granulair
  (`date_ams >= vandaag`), want zonder tijd valt niet te bepalen of een wedstrijd vandaag al voorbij is.
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

### 3.3 ~~ESPN-tv-uitzendgids~~ — [DROP]
`gids-grab`/`gids-read`/`espn.json`/`simple_html_dom` en de `espn/`-kanaallogo's vervallen. Het
schema toont **geen uitzendkanaal-indicatie** meer.

### 3.4 ~~tvgids.nl~~ — [DROP]
In legacy al dode code (`site.php` laadt `tvgidsnl.json` niet). Volledig verwijderd.

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
- ~~`espnpsmatchtimes`~~ **[DROP]** (hoorde bij de tv-gids-matching).
- ~~`espnmatchtvgidsinps`~~ **[DROP]** (tvgids.nl).

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
→ alles uit + opslaan; cross-tab via `storage`.

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

---

## 9. Graceful degradation [NEW]
- **Geen/oude MLB-scheduledata:** schema rendert lege staat (§5.8); build faalt niet.
- **Geen ESPN-API-data in postseason:** val terug op date-derived ronde-labels (§5.6 stap 2);
  geen serie-stand.
- **MLB Stats API onbereikbaar (client):** scores/standen tonen cache + offline-melding.
- **Tail-JSON onbereikbaar (client):** "meer laden" meldt dat het offline niet lukt; de inline
  beginbatch blijft staan (§5.9).

---

## 10. Jaarlijks onderhoud
Nieuw `start[YYYY]`-blok (alle verplichte datums + uitzonderingen). Config-validatie (§4.3) vangt
ontbrekende/ongeldige velden. Controleer standaardtab, datumkoppen, `debug.html`.

---

## 11. Toekomstige uitbreiding: AI-interessantheid [NEW]
`Game.enrichment` is de toetsbare haak: een optioneel veld dat een latere build-stap vult
(bv. `{score: float, label: str, reasons: [str]}`). Renderlaag toont het als badge en/of extra
sorteersleutel. Zonder verrijkingsstap blijft het veld `None` en heeft het geen zichtbaar effect.
Acceptatie:
het wedstrijdmodel en de renderfunctie accepteren een gevulde `enrichment` zonder de overige
rendering te veranderen.

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
