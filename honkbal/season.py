from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from honkbal.clock import AMSTERDAM, Clock
from honkbal.config.seasons import RAW_SEASONS
from honkbal.config.toggles import TEST_NEXT_SEASON

REQUIRED_KEYS: tuple[str, ...] = (
    "reg", "showfrom", "einde", "ps", "wc", "ds", "cs", "ws", "new", "hide",
)
OPTIONAL_DATE_KEYS: tuple[str, ...] = ("newreg", "allstargame")

# In-season datums horen bij het blokjaar; next-season datums bij blokjaar + 1 (SPEC §4.3).
IN_SEASON_KEYS: frozenset[str] = frozenset(
    {"reg", "showfrom", "einde", "ps", "wc", "ds", "cs", "ws", "allstargame"}
)
NEXT_SEASON_KEYS: frozenset[str] = frozenset({"new", "hide", "newreg"})


class ConfigError(Exception):
    """Ongeldige of onvolledige seizoensconfiguratie; stopt de build."""


def parse_date_nl(s: str) -> datetime:
    # strptime met %d-%m-%Y weigert 30-02 (geen stille rollover zoals PHP).
    naive = datetime.strptime(s, "%d-%m-%Y")
    return naive.replace(tzinfo=AMSTERDAM)


class SeasonWindows(BaseModel):
    model_config = ConfigDict(frozen=True)

    reg: datetime
    showfrom: datetime
    einde: datetime
    ps: datetime
    wc: datetime
    ds: datetime
    cs: datetime
    ws: datetime
    new: datetime
    hide: datetime
    newreg: datetime | None = None
    allstargame: datetime | None = None
    uitzondering: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_invariants(self) -> SeasonWindows:
        if not (self.showfrom <= self.einde):
            raise ValueError("showfrom > einde")
        if not (self.reg <= self.ps <= self.einde):
            raise ValueError("reg <= ps <= einde geschonden")
        for naam, ronde in (("wc", self.wc), ("ds", self.ds), ("cs", self.cs), ("ws", self.ws)):
            if not (self.ps <= ronde <= self.einde):
                raise ValueError(f"ronde {naam} buiten [ps, einde]")
        if not (self.new < self.hide):
            raise ValueError("new >= hide")
        if self.newreg is not None and not (self.new < self.newreg):
            raise ValueError("new >= newreg")
        return self


def load_windows(year: int, raw: dict = RAW_SEASONS) -> SeasonWindows:
    if year not in raw:
        raise ConfigError(f"Geen seizoensblok voor jaar {year}")
    block = raw[year]
    missing = [k for k in REQUIRED_KEYS if k not in block]
    if missing:
        raise ConfigError(f"Jaar {year} mist verplichte velden: {', '.join(missing)}")

    parsed: dict[str, object] = {}
    for key in (*REQUIRED_KEYS, *OPTIONAL_DATE_KEYS):
        if key in block:
            try:
                parsed[key] = parse_date_nl(str(block[key]))
            except ValueError as exc:
                msg = f"Jaar {year} veld '{key}': ongeldige datum {block[key]!r}"
                raise ConfigError(msg) from exc

    # Jaar-invariant: in-season datums in blokjaar, next-season datums in blokjaar + 1 (SPEC §4.3).
    for key, dt in parsed.items():
        assert isinstance(dt, datetime)
        if key in IN_SEASON_KEYS and dt.year != year:
            raise ConfigError(
                f"Jaar {year} veld '{key}': jaar {dt.year} hoort {year} te zijn (in-season)"
            )
        if key in NEXT_SEASON_KEYS and dt.year != year + 1:
            raise ConfigError(
                f"Jaar {year} veld '{key}': jaar {dt.year} hoort {year + 1} te zijn (next-season)"
            )

    uitz = tuple(s for s in block.get("uitzondering", []) if s)
    try:
        return SeasonWindows(uitzondering=uitz, **parsed)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise ConfigError(f"Jaar {year}: invariant geschonden — {exc}") from exc


class ActiveSeason(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int
    next_year: int
    windows: SeasonWindows
    next_uitzondering: tuple[str, ...]
    no_grab: bool


def select_active_season(
    clock: Clock,
    raw: dict = RAW_SEASONS,
    *,
    test_next_season: bool = TEST_NEXT_SEASON,
) -> ActiveSeason:
    now = clock.now()
    year = now.year + 1 if test_next_season else now.year

    # LEGACY (config.php:198): next_year wordt vóór de fallback/rollover berekend, op het
    # kalenderjaar-afgeleide `year`. Bewuste keuze (geen FIX): na een rollover hieronder kan
    # next_year daardoor gelijk aan `year` worden — exact het huidige sitegedrag.
    next_year = year + 1

    if year not in raw:
        year -= 1

    windows = load_windows(year, raw)
    if now >= windows.einde:
        year += 1
        windows = load_windows(year, raw)

    # Lees ALLEEN het uitzondering-veld van next_year — geen volledige validatie van een mogelijk
    # nog onvolledig next-year-blok (anders breekt dat de selectie van het huidige seizoen).
    next_uitz: tuple[str, ...] = ()
    if next_year in raw:
        next_uitz = tuple(s for s in raw[next_year].get("uitzondering", []) if s)

    half_jan = parse_date_nl(f"15-01-{year}")
    no_grab = (now >= windows.einde or now < half_jan) and not test_next_season

    return ActiveSeason(
        year=year,
        next_year=next_year,
        windows=windows,
        next_uitzondering=next_uitz,
        no_grab=no_grab,
    )
