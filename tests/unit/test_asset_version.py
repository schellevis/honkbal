import os

from honkbal.cli_version import resolve_asset_version


def test_reads_version_txt_when_present(tmp_path):
    vf = tmp_path / "version.txt"
    vf.write_text("abc123def456-42\n")
    css = tmp_path / "style.css"
    css.write_text("body{}")
    assert resolve_asset_version(version_file=vf, style_css=css) == "abc123def456-42"


def test_falls_back_to_style_mtime_when_no_version(tmp_path):
    vf = tmp_path / "version.txt"  # bestaat niet
    css = tmp_path / "style.css"
    css.write_text("body{}")
    os.utime(css, (1_700_000_000, 1_700_000_000))
    assert resolve_asset_version(version_file=vf, style_css=css) == "1700000000"


def test_empty_version_txt_falls_back(tmp_path):
    vf = tmp_path / "version.txt"
    vf.write_text("   \n")  # leeg/whitespace
    css = tmp_path / "style.css"
    css.write_text("x")
    os.utime(css, (1_700_000_001, 1_700_000_001))
    assert resolve_asset_version(version_file=vf, style_css=css) == "1700000001"
