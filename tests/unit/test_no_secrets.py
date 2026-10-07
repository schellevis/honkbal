import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
# Sla gegenereerde/vendor-mappen over.
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "docs", "docs_v2", ".data",
    "__pycache__", ".pytest_cache", ".ruff_cache", "tvcache",
}
SECRET_PATTERNS = [
    re.compile(r"AccountKey\s*=", re.I),                # Cloudflare/Azure-achtig
    re.compile(r"-----BEGIN ((RSA|EC|DSA|OPENSSH|ENCRYPTED|PGP) )?PRIVATE KEY( BLOCK)?-----"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),             # Google/Firebase API key
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),        # Slack token
    re.compile(r"hooks\.slack\.com/services/T[0-9A-Z]+/"),  # Slack-webhook
    re.compile(r"discord(app)?\.com/api/webhooks/\d+/"),  # Discord-webhook
    re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),          # GitHub PAT/OAuth/app-token
    re.compile(r"github_pat_[0-9A-Za-z_]{40,}"),        # GitHub fine-grained PAT
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),         # AWS access key id
    re.compile(r"\bsk-(ant-|proj-)?[0-9A-Za-z_\-]{20,}"),  # Anthropic/OpenAI API key
    re.compile(r"\b[rs]k_live_[0-9A-Za-z]{20,}"),       # Stripe live key
    re.compile(r"\bnpm_[0-9A-Za-z]{36}\b"),             # npm token
    re.compile(r"\bpypi-AgE[0-9A-Za-z_\-]{50,}"),       # PyPI token
    re.compile(r"\beyJ[0-9A-Za-z_\-]{10,}\.eyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}"),  # JWT
    # Deploy-secrets van deze repo horen alleen als ${{ secrets.X }} in workflows.
    re.compile(
        r"\b(VERCEL_TOKEN|VERCEL_ORG_ID|VERCEL_PROJECT_ID|BUNNY_API_KEY|BUNNY_PULLZONE_ID)"
        r"\b\s*[:=]\s*[\"']?(?!\$)[0-9A-Za-z_\-]{6,}"
    ),
]

# Bestanden die nooit getrackt mogen worden (accountconfig, sleutels, lokale instellingen).
FORBIDDEN_TRACKED = [
    re.compile(r"(^|/)\.env(\.[^/]*)?$"),
    re.compile(r"(^|/)\.vercel/"),
    re.compile(r"(^|/)\.claude/settings\.local\.json$"),
    re.compile(r"(^|/)id_(rsa|ecdsa|ed25519|dsa)$"),
    re.compile(r"\.(pem|key|p12|pfx|keystore)$"),
    re.compile(r"(^|/)\.(npmrc|pypirc|netrc)$"),
    re.compile(r"(^|/)(\.data|docs)/"),
    re.compile(r"(^|/)version\.txt$"),
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


def _git_tracked():
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("geen git-checkout")
    return [f for f in out.decode().split("\0") if f]


def test_no_forbidden_tracked_files():
    offenders = [
        f for f in _git_tracked() if any(pat.search(f) for pat in FORBIDDEN_TRACKED)
    ]
    assert not offenders, "bestanden die niet getrackt mogen worden:\n" + "\n".join(offenders)


# Synthetische voorbeelden, in stukken opgebouwd zodat dit bestand zelf niet matcht.
_SAMPLES = [
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "-----BEGIN " + "PRIVATE KEY-----",
    "AI" + "za" + "A" * 35,
    "xo" + "xb-" + "1" * 12,
    "hooks.slack.com/services/" + "T0000/B0000/xyz",
    "discord.com/api/web" + "hooks/123/abc",
    "gh" + "p_" + "a" * 36,
    "gh" + "s_" + "a" * 36,
    "github" + "_pat_" + "a" * 60,
    "AK" + "IA" + "A" * 16,
    "s" + "k-ant-" + "a" * 40,
    "s" + "k-proj-" + "a" * 40,
    "s" + "k_live_" + "a" * 24,
    "n" + "pm_" + "a" * 36,
    "py" + "pi-AgE" + "a" * 60,
    "ey" + "J" + "a" * 20 + ".ey" + "J" + "b" * 20 + "." + "c" * 20,
    "VERCEL" + "_TOKEN=" + "abcdef123456",
    "BUNNY" + "_API_KEY: " + "'0000-1111-2222'",
]

_HARMLESS = [
    "VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}",
    'ESPN_WATCH_API_KEY = "0dbf88e8-cc6d-41da-aa83-18b5c630bc5c"',  # publieke constante
    "task-runner",
    "risk-assessment-pipeline-overview",
]


@pytest.mark.parametrize("sample", _SAMPLES)
def test_secret_patterns_detect_samples(sample):
    assert any(pat.search(sample) for pat in SECRET_PATTERNS), sample


@pytest.mark.parametrize("sample", _HARMLESS)
def test_secret_patterns_ignore_harmless(sample):
    assert not any(pat.search(sample) for pat in SECRET_PATTERNS), sample


@pytest.mark.parametrize(
    "path,forbidden",
    [
        (".env", True), ("sub/.env.local", True), (".vercel/project.json", True),
        (".claude/settings.local.json", True), ("deploy/key.pem", True),
        ("docs/index.html", True), ("version.txt", True),
        (".env.example.md/x", False), ("honkbal/env.py", False),
        ("deploy/vercel/config.json", False), ("SPEC.md", False),
    ],
)
def test_forbidden_tracked_patterns(path, forbidden):
    assert any(pat.search(path) for pat in FORBIDDEN_TRACKED) is forbidden
