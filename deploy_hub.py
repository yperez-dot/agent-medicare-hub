#!/usr/bin/env python3
"""
Agent Hub — Netlify Deploy Script
===================================
CRITICAL RULE (from MEMORY.md + July 27 & Aug 3 outages):
  - pages/ is the zip ROOT (index.html must be at zip root, not hub-migration/pages/index.html)
  - files/ goes in as /files/ subdirectory
  - NEVER zip hub-migration/ as root — instant 404

Run:  python3 deploy_hub.py
"""

import os, sys, zipfile, tempfile, hashlib, requests, json

SITE_ID   = "fba5b50f-a619-46aa-97d4-2b660a4959ca"
TOKEN_FILE = os.path.expanduser("~/.openclaw/credentials/netlify-token.txt")
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR  = os.path.join(BASE_DIR, "pages")
FILES_DIR  = os.path.join(BASE_DIR, "files")

def load_token():
    with open(TOKEN_FILE) as f:
        for line in f:
            if line.startswith("NETLIFY_HUB_TOKEN="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("NETLIFY_HUB_TOKEN not found in token file")

def build_zip(tmp_path):
    """
    Zip structure (MUST be this or site 404s):
      index.html          ← from pages/index.html
      *.html              ← all other pages/
      files/              ← from files/
    """
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add pages/ as root
        for root, dirs, fnames in os.walk(PAGES_DIR):
            for fname in fnames:
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, PAGES_DIR)
                zf.write(full, arcname)

        # Add files/ as /files/
        for root, dirs, fnames in os.walk(FILES_DIR):
            for fname in fnames:
                full = os.path.join(root, fname)
                arcname = os.path.join("files", os.path.relpath(full, FILES_DIR))
                zf.write(full, arcname)

    # Sanity check — index.html must be at root
    with zipfile.ZipFile(tmp_path) as zf:
        names = zf.namelist()
        if "index.html" not in names:
            raise RuntimeError(
                f"ABORT: index.html not at zip root! Names: {names[:10]}\n"
                "Check PAGES_DIR path — likely zipped wrong directory."
            )
        print(f"✅ Zip OK — {len(names)} files, index.html at root")

def deploy(token, zip_path):
    with open(zip_path, "rb") as f:
        data = f.read()

    print("Uploading to Netlify...")
    resp = requests.post(
        f"https://api.netlify.com/api/v1/sites/{SITE_ID}/deploys",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/zip",
        },
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    state = result.get("state")
    deploy_id = result.get("id")
    print(f"Deploy ID: {deploy_id} | State: {state}")

    if state not in ("ready", "uploaded", "processing"):
        raise RuntimeError(f"Unexpected deploy state: {state}\n{json.dumps(result, indent=2)}")

    return deploy_id

def verify():
    import time
    print("Verifying live site...")
    time.sleep(4)
    r = requests.get("https://agentmedicarehub.com", timeout=15)
    if r.status_code == 200:
        print(f"✅ agentmedicarehub.com → {r.status_code}")
    else:
        raise RuntimeError(f"❌ Site returned {r.status_code} — check Netlify dashboard!")

if __name__ == "__main__":
    token = load_token()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        build_zip(tmp_path)
        deploy_id = deploy(token, tmp_path)
        verify()
        print("✅ Hub deployed successfully.")
    finally:
        os.unlink(tmp_path)
