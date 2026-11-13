#!/usr/bin/env python3
"""Run: python3 watch/test_check.py  (no network, no dependency)."""
import tempfile
from pathlib import Path

from check import check, diff_excerpt, extract, fingerprint

PAGE = """<html><head><style>.x{}</style><script>var csrf="abc123";</script></head>
<body><nav>Menu</nav><h1>Webhook</h1><p>Header: <code>X-Secret-Key</code> &amp; HMAC</p>
<form><input name="token" value="random-123"><select><option>Orange Money</option></select>
<button>Payer</button></form><!-- build 42 --><p>Status:   succeeded</p></body></html>"""


def test_extract_keeps_docs_and_drops_volatile_parts():
    text = extract(PAGE, drop_patterns=[r"^Status:"])
    assert "Webhook" in text and "Header: X-Secret-Key & HMAC" in text
    for noise in ("csrf", "Menu", "random-123", "Orange Money", "Payer", "build 42", ".x{}", "succeeded"):
        assert noise not in text, noise


def test_extract_is_stable_when_only_noise_changes():
    other = PAGE.replace("abc123", "zzz999").replace("random-123", "random-456").replace("build 42", "build 43")
    assert fingerprint(extract(PAGE)) == fingerprint(extract(other))


def test_extract_markdown_passthrough():
    assert extract("# Title\n\n  Use   `X-Secret-Key`\n") == "# Title\nUse `X-Secret-Key`\n"


def test_check_new_same_changed():
    entry = {"id": "demo", "url": "https://example.test/doc"}
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp)
        assert check(entry, lambda u: "<p>v1</p>", state) == ("new", "")
        assert check(entry, lambda u: "<p>v1</p>", state) == ("same", "")
        status, diff = check(entry, lambda u: "<p>v2</p>", state)
        assert status == "changed" and "-v1" in diff and "+v2" in diff
        assert (state / "demo.txt").read_text() == "v2\n"


def test_diff_excerpt_is_truncated():
    old = "\n".join(f"line {i}" for i in range(200))
    new = "\n".join(f"LINE {i}" for i in range(200))
    out = diff_excerpt(old, new, max_lines=10)
    assert out.count("\n") == 10 and out.endswith("more diff lines)")


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} tests passed")
