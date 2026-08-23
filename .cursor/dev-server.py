#!/usr/bin/env python3
"""
Agent Medicare Hub — local development server
=============================================
Serves the static hub exactly the way Netlify does in production so that
previews match the live site:

  * pages/          -> site root            (e.g. /home.html, /login.html)
  * files/          -> /files/*             (PDFs, images, docx, etc.)
  * sep-tracker/    -> /sep-tracker/*       (standalone sub-app, optional)
  * "pretty" URLs   -> /home  serves pages/home.html   (Netlify clean URLs)
  * _redirects      -> honored for simple `from to 200` rewrite rules

This mirrors .github/workflows/deploy.yml (which copies pages/. to the publish
root and files/ into /files/) without needing a build step, so edits under
pages/ and files/ are served live.

Run:  python3 .cursor/dev-server.py           # listens on 0.0.0.0:8000
      PORT=9000 python3 .cursor/dev-server.py  # custom port
"""

import os
import re
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(REPO_ROOT, "pages")
FILES_DIR = os.path.join(REPO_ROOT, "files")
SEP_DIR = os.path.join(REPO_ROOT, "sep-tracker")
PORT = int(os.environ.get("PORT", "8000"))


def load_redirects():
    """Parse pages/_redirects for simple `from to [status]` 200-rewrite rules."""
    rules = {}
    path = os.path.join(PAGES_DIR, "_redirects")
    if not os.path.isfile(path):
        return rules
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                src, dst = parts[0], parts[1]
                rules[src.rstrip("/")] = dst
    return rules


REDIRECTS = load_redirects()


class HubHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Resolve to a filesystem path using Netlify-like routing.
        parsed = urlparse(path)
        url_path = unquote(parsed.path)

        # Apply simple _redirects rewrites (e.g. /certs -> /certs.html).
        if url_path.rstrip("/") in REDIRECTS:
            url_path = REDIRECTS[url_path.rstrip("/")]

        # Normalize and strip any leading slash for joining.
        clean = posixpath.normpath(url_path)
        clean = clean.lstrip("/")

        # Route by top-level prefix to the right source directory.
        if clean == "files" or clean.startswith("files/"):
            return os.path.join(FILES_DIR, clean[len("files/"):].lstrip("/") or ".")
        if clean == "sep-tracker" or clean.startswith("sep-tracker/"):
            rest = clean[len("sep-tracker"):].lstrip("/")
            return os.path.join(SEP_DIR, rest) if rest else os.path.join(SEP_DIR, "index.html")

        # Everything else is served from pages/ (the site root).
        candidate = os.path.join(PAGES_DIR, clean) if clean else PAGES_DIR

        if os.path.isdir(candidate):
            index = os.path.join(candidate, "index.html")
            if os.path.isfile(index):
                return index
            return candidate

        if os.path.isfile(candidate):
            return candidate

        # Netlify "pretty URLs": /home -> pages/home.html when no extension.
        if not os.path.splitext(candidate)[1]:
            html_candidate = candidate + ".html"
            if os.path.isfile(html_candidate):
                return html_candidate

        return candidate

    def end_headers(self):
        # Disable caching so live edits show up immediately during development.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    os.chdir(REPO_ROOT)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HubHandler)
    print(f"Agent Medicare Hub dev server running at http://localhost:{PORT}")
    print(f"  root (pages/):    http://localhost:{PORT}/")
    print(f"  login:            http://localhost:{PORT}/login.html")
    print(f"  files/ mount:     http://localhost:{PORT}/files/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
