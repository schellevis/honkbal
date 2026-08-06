from pathlib import Path

from honkbal.render.logos import channel_logo_html, display_name, logo_html

IMG = Path(__file__).parent.parent / "fixtures" / "img"


def test_dark_mode_picture_when_dark_exists():
    html = str(logo_html("Yankees", img_dir=IMG, asset_version="v1"))
    assert "<picture" in html
    assert 'media="(prefers-color-scheme: dark)"' in html
    assert "/img/yankees-dark.png?v1" in html
    assert "/img/yankees-fs8.png?v1" in html
    assert 'alt="Yankees"' in html


def test_plain_img_when_no_dark():
    html = str(logo_html("Red Sox", img_dir=IMG, asset_version="v1"))
    assert "<picture" not in html
    assert "/img/red+sox-fs8.png?v1" in html


def test_text_fallback_when_no_logo_file():
    html = str(logo_html("Mets", img_dir=IMG, asset_version="v1"))
    assert 'class="logofill mets"' in html
    assert "<img" not in html


def test_text_fallback_escapes_untrusted_class_input():
    html = str(logo_html('x" onmouseover="alert(1)', img_dir=IMG, asset_version="v1"))
    assert 'onmouseover=' not in html
    assert 'class="logofill unknown"' in html


def test_allstar_league_mapping():
    assert display_name("AL All-Stars") == "American League"
    assert display_name("NL All-Stars") == "National League"
    html = str(logo_html("AL All-Stars", img_dir=IMG, asset_version="v1"))
    assert "/img/american+league-fs8.png?v1" in html
    assert 'alt="American League"' in html


def test_real_team_keeps_own_name():
    assert display_name("Yankees") == "Yankees"


def test_channel_logo_with_dark_variant_and_nl_badge():
    html = str(channel_logo_html("espn2", img_dir=IMG, asset_version="v1", nl_commentary=True))
    assert html.startswith('<div class="espn" data-channel="espn2" data-nlcom="1">')
    assert '<span class="comm">NL</span>' in html
    assert '<source srcset="/img/espn/espn2-dark.png?v1"' in html
    assert 'media="(prefers-color-scheme: dark)"' in html
    assert '<img class="espn2" src="/img/espn/espn2.png?v1" alt="ESPN2" />' in html


def test_channel_logo_light_only_without_badge():
    html = str(channel_logo_html("espn", img_dir=IMG, asset_version="v1"))
    assert "<picture" not in html
    assert "data-nlcom" not in html
    assert '<span class="comm">' not in html
    assert '<img class="espn" src="/img/espn/espn.png?v1" alt="ESPN" />' in html


def test_channel_logo_empty_for_unknown_channel_or_missing_asset():
    # espn9 staat niet in de allowlist; espn3 heeft geen fixture-PNG.
    assert str(channel_logo_html("espn9", img_dir=IMG, asset_version="v1")) == ""
    assert str(channel_logo_html("espn3", img_dir=IMG, asset_version="v1")) == ""
