#!/usr/bin/env python3
"""Weekly doc watch: fetch each page in watch/docs.json, extract its useful text,
compare with watch/state/<id>.txt, update the state and write a Markdown report
of what changed. No AI, no third-party dependency.

Usage: python3 watch/check.py [report_path]
Exit code is 0; the report file exists only if something changed or failed.
"""
import difflib
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
MAX_DIFF_LINES = 60

# Blocks that are never documentation: scripts, styles, navigation chrome and
# interactive forms (the PayTech page embeds a live test form).
DROP_BLOCKS = re.compile(
    r"(?is)<(script|style|noscript|svg|form|select|textarea|button|nav|footer|header)\b.*?</\1\s*>"
)


def extract(raw, drop_patterns=()):
    """Return normalized, line-based text: tags removed, entities decoded,
    whitespace collapsed, lines matching drop_patterns removed."""
    text = DROP_BLOCKS.sub("\n", raw)
    text = re.sub(r"(?s)<!--.*?-->", "", text)
    text = re.sub(r"(?i)<(br|p|div|li|tr|h[1-6]|pre|table|section|article)\b[^>]*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    drops = [re.compile(p) for p in drop_patterns]
    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line and not any(d.search(line) for d in drops):
            lines.append(line)
    return "\n".join(lines) + "\n"


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def diff_excerpt(old, new, max_lines=MAX_DIFF_LINES):
    """Unified diff limited to max_lines; empty string if identical."""
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "before", "after", lineterm="", n=1))
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more diff lines)"]
    return "\n".join(lines)


def fetch(url):
    # Plain curl: default user agent, follow redirects, fail on HTTP errors.
    out = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--max-time", "60", "--retry", "2", url],
        capture_output=True,
        timeout=200,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip() or f"curl exit {out.returncode}")
    return out.stdout.decode("utf-8", "replace")


def check(entry, fetcher=fetch, state_dir=STATE):
    """Return (status, detail) with status in new|same|changed and update state."""
    text = extract(fetcher(entry["url"]), entry.get("drop", []))
    path = state_dir / f"{entry['id']}.txt"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old is not None and fingerprint(old) == fingerprint(text):
        return "same", ""
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if old is None:
        return "new", ""
    return "changed", diff_excerpt(old, text)


def main():
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "report.md"
    docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
    changed, failed = [], []
    for provider, entries in docs.items():
        for entry in entries:
            try:
                status, detail = check(entry)
            except Exception as exc:  # report and keep going
                failed.append((provider, entry["url"], str(exc)))
                print(f"FAIL    {entry['id']}: {exc}")
                continue
            print(f"{status:7} {entry['id']}")
            if status == "changed":
                changed.append((provider, entry["url"], detail))

    if not changed and not failed:
        report_path.unlink(missing_ok=True)
        return
    parts = []
    for provider, url, detail in changed:
        parts.append(f"### {provider}\n\n{url}\n\n```diff\n{detail}\n```\n")
    if failed:
        parts.append("### Fetch failures\n\n" + "\n".join(f"- {p}: {u} ({e})" for p, u, e in failed) + "\n")
    report_path.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
