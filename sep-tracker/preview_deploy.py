#!/usr/bin/env python3
"""Create a Netlify *draft* deploy of the Agent Medicare Hub. Never production.

Usage (from the repo root):
  NETLIFY_AUTH_TOKEN=... python3 sep-tracker/preview_deploy.py

The token is read from the environment (NETLIFY_HUB_TOKEN, NETLIFY_AUTH_TOKEN_NEW,
or NETLIFY_AUTH_TOKEN). This script does not print the token.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGES = REPO / "pages"
FILES = REPO / "files"
SITE_ID = "fba5b50f-a619-46aa-97d4-2b660a4959ca"


def token() -> str:
    for name in ("NETLIFY_HUB_TOKEN", "NETLIFY_AUTH_TOKEN_NEW", "NETLIFY_AUTH_TOKEN"):
        val = os.environ.get(name)
        if val:
            return val
    # Optional OpenClaw credential file — do not print contents
    cred = Path.home() / ".openclaw" / "credentials" / "netlify-token.txt"
    if cred.exists():
        for line in cred.read_text().splitlines():
            if line.startswith("NETLIFY_HUB_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("No Netlify token in the environment. Set NETLIFY_HUB_TOKEN (do not paste it in chat).")


def main() -> int:
    if "--prod" in sys.argv or "--production" in sys.argv:
        raise SystemExit("Refusing --prod. This script is preview-only. Production deploys need Yahoska's explicit yes.")
    tok = token()
    staging = Path(tempfile.mkdtemp(prefix="hub-preview-"))
    # Mirror deploy_hub.py layout: pages/ at zip root, files/ under /files/
    for src_root, dest_root in ((PAGES, staging), (FILES, staging / "files")):
        if not src_root.exists():
            continue
        for path in src_root.rglob("*"):
            if path.is_file():
                dest = dest_root / path.relative_to(src_root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(path.read_bytes())
    print(f"Draft-deploying {SITE_ID} from {staging} (not production)")
    env = os.environ.copy()
    env["NETLIFY_AUTH_TOKEN"] = tok
    proc = subprocess.run(
        ["netlify", "deploy", "--dir", str(staging), "--site", SITE_ID, "--json"],
        env=env,
        capture_output=True,
        text=True,
    )
    # Print only the draft/deploy URL, never the token or raw env
    out = proc.stdout or ""
    err = proc.stderr or ""
    if proc.returncode != 0:
        # Redact any accidental token echo
        for blob in (out, err):
            cleaned = blob.replace(tok, "[redacted]")
            if cleaned.strip():
                print(cleaned[-2000:], file=sys.stderr)
        return proc.returncode
    import json, re
    url = None
    try:
        data = json.loads(out)
        url = data.get("deploy_url") or data.get("url") or data.get("ssl_url")
        deploy_id = data.get("id") or data.get("deploy_id")
        print("draft deploy id:", deploy_id)
        print("preview url:", url)
    except json.JSONDecodeError:
        m = re.search(r"https://[^\s]+", out)
        print(out)
        if m:
            print("preview url:", m.group(0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
