from pathlib import Path

from honkbal.render.logos import display_name, logo_html

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
