#!/usr/bin/env python3
"""Fail if pages/sep-tracker-app.html has invalid inline DATA or JS.

Used by deploy_hub.py and GitHub Actions so a raw newline in var DATA
cannot be published again.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "pages" / "sep-tracker-app.html"


def extract_data(html: str) -> str:
    m = re.search(r"var DATA=(\[.*?\]);", html, re.S)
    if not m:
        raise SystemExit("validate_embedded_data: no var DATA=[...] found")
    return m.group(1)


def extract_js_scripts(html: str) -> list[str]:
    scripts = []
    for m in re.finditer(r"<script(\s[^>]*)?>(.*?)</script>", html, re.S | re.I):
        attrs = m.group(1) or ""
        if re.search(r'type\s*=\s*["\']application/json["\']', attrs, re.I):
            continue
        if re.search(r'\bsrc\s*=', attrs, re.I):
            continue
        body = m.group(2).strip()
        if body:
            scripts.append(body)
    return scripts


def main() -> int:
    html = APP.read_text()
    raw = extract_data(html)
    try:
        data = json.loads(raw, strict=True)
    except json.JSONDecodeError as e:
        print(f"validate_embedded_data: DATA is not strict JSON: {e}", file=sys.stderr)
        return 1
    if not isinstance(data, list) or not data:
        print("validate_embedded_data: DATA must be a non-empty array", file=sys.stderr)
        return 1

    scripts = extract_js_scripts(html)
    if not scripts:
        print("validate_embedded_data: no inline JavaScript found", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        js_path = Path(tmp) / "sep-tracker-app.js"
        js_path.write_text("\n;\n".join(scripts) + "\n")
        proc = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            print(f"validate_embedded_data: node --check failed:\n{err}", file=sys.stderr)
            return 1

    print(f"validate_embedded_data: ok — {len(data)} SEPs, node --check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
