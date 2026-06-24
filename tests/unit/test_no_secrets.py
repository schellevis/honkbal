import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
# Sla gegenereerde/vendor-mappen over.
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "docs", "docs_v2", ".data",
    "__pycache__", ".pytest_cache", ".ruff_cache", "tvcache",
}
SECRET_PATTERNS = [
    re.compile(r"AccountKey\s*=", re.I),                # Cloudflare/Azure-achtig
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),             # Google/Firebase API key
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),        # Slack token
    re.compile(r"ghp_[0-9A-Za-z]{30,}"),                # GitHub PAT
]


def _scan_files():
    for p in REPO.rglob("*"):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in {".png", ".ico", ".woff", ".woff2", ".jpg", ".gif"}:
            continue
        yield p


def test_no_cloudflare_script_in_tree():
    assert not (REPO / "cloudflare.sh").exists(), (
        "cloudflare.sh mag niet in v2 bestaan (SPEC §13)"
    )


def test_no_plaintext_secrets():
    offenders = []
    for p in _scan_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                offenders.append(f"{p.relative_to(REPO)} :: {pat.pattern}")
    assert not offenders, "mogelijke secrets gevonden:\n" + "\n".join(offenders)
