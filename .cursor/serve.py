#!/usr/bin/env python3
"""
Local dev server for the Agent Medicare Hub static site.

Reproduces the Netlify publish layout used in production (see netlify.toml,
deploy_hub.py and .github/workflows/deploy.yml):

  * pages/ is the web root (index.html lives at "/")
  * files/ is served under "/files/"
  * pages/_redirects rules are applied (e.g. /certs -> /certs.html)
  * Netlify-style "clean URLs": /foo serves /foo.html when it exists

Usage:  python3 .cursor/serve.py [--port 8080] [--host 0.0.0.0]
"""
from __future__ import annotations

import argparse
import os
import posixpath
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(REPO_ROOT, "pages")
FILES_DIR = os.path.join(REPO_ROOT, "files")
SEP_TRACKER_DIR = os.path.join(REPO_ROOT, "sep-tracker")
REDIRECTS_FILE = os.path.join(PAGES_DIR, "_redirects")


def load_redirects() -> list[tuple[str, str, int]]:
    """Parse the Netlify _redirects file into (from, to, status) tuples."""
    rules: list[tuple[str, str, int]] = []
    if not os.path.exists(REDIRECTS_FILE):
        return rules
    with open(REDIRECTS_FILE, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            src, dst = parts[0], parts[1]
            status = 301
            if len(parts) >= 3 and re.fullmatch(r"\d+!?", parts[2]):
                status = int(parts[2].rstrip("!"))
            rules.append((src, dst, status))
    return rules


REDIRECTS = load_redirects()


class HubHandler(SimpleHTTPRequestHandler):
    """Serve pages/ as root, files/ under /files/, and apply _redirects."""

    def translate_path(self, path: str) -> str:
        parsed = urlsplit(path).path
        clean = posixpath.normpath(parsed)

        if clean == "/files" or clean.startswith("/files/"):
            rel = clean[len("/files"):].lstrip("/")
            return os.path.join(FILES_DIR, rel)

        if clean == "/sep-tracker" or clean.startswith("/sep-tracker/"):
            rel = clean[len("/sep-tracker"):].lstrip("/")
            return os.path.join(SEP_TRACKER_DIR, rel)

        rel = clean.lstrip("/")
        return os.path.join(PAGES_DIR, rel)

    def _resolve_redirect(self, path: str) -> tuple[str, int] | None:
        req = urlsplit(path).path
        for src, dst, status in REDIRECTS:
            if req == src:
                return dst, status
        return None

    def _maybe_clean_url(self) -> None:
        """Netlify serves /foo as foo.html when foo.html exists."""
        req = urlsplit(self.path).path
        if req.endswith("/") or "." in posixpath.basename(req):
            return
        candidate = self.translate_path(self.path) + ".html"
        if os.path.isfile(candidate):
            self.path = req + ".html"

    def do_GET(self) -> None:
        redirect = self._resolve_redirect(self.path)
        if redirect is not None:
            dst, status = redirect
            if status in (200, 0):
                self.path = dst
            else:
                self.send_response(status)
                self.send_header("Location", dst)
                self.end_headers()
                return
        self._maybe_clean_url()
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        super().log_message(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Medicare Hub dev server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    args = parser.parse_args()

    handler = partial(HubHandler, directory=PAGES_DIR)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Agent Medicare Hub dev server running on http://{args.host}:{args.port}")
    print(f"  web root : {PAGES_DIR}")
    print(f"  /files/  : {FILES_DIR}")
    print(f"  redirects: {len(REDIRECTS)} rule(s) from pages/_redirects")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dev server.")
        server.shutdown()


if __name__ == "__main__":
    main()
