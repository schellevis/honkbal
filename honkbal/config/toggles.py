from __future__ import annotations

SHOW_GAMES = 250
LOAD_MORE_BATCH = 250
SLEEP_SECONDS = 2
GRAB_NO_WAIT = False
ESPNCAP = 3000  # seconden
COUNTDOWN_FROM = (1, 1)  # (dag, maand)
TEST_NEXT_SEASON = False
LIVE_GRACE_HOURS = 4  # getimede games blijven zichtbaar tot dit aantal uren na de starttijd
LIVE_WINDOW_HOURS = 5  # live-sectie: poll-venster per game = [start, start + dit aantal uren]
LIVE_POLL_HORIZON_HOURS = 48  # live-sectie: hoever vooruit starttijden in de HTML meegaan
TV_GUIDE_DAYS = 4  # tv-gids: aantal dagen vooruit ophalen (vandaag t/m +3)
TV_MATCH_TOLERANCE_MIN = 75  # tv-gids: max. verschil game-start vs. uitzending-start (minuten)
