#!/usr/bin/env python3
"""Local server for PM editable HTML docs — serves pages and writes edits back to disk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from flask import Flask, abort, jsonify, request, send_from_directory
except ImportError:
    Flask = None

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "pages"
ASSETS_DIR = ROOT / "assets"

ALLOWED_PAGES = {
    "skill1.html",
    "skill-io-review.html",
}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        pages = []
        for name in sorted(ALLOWED_PAGES):
            title = name.replace(".html", "").replace("-", " ")
            pages.append({"name": name, "title": title, "url": f"/pages/{name}"})
        rows = "".join(
            f'<li><a href="{p["url"]}">{p["title"]}</a> <code>{p["name"]}</code></li>'
            for p in pages
        )
        return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>PM Docs</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background:#1a1a1e; color:#e0e0e8; padding:40px; line-height:1.7; }}
a {{ color:#378ADD; }}
code {{ color:#9898a8; font-size:12px; }}
</style></head><body>
<h1>PM 文档工作台</h1>
<p>通过本地服务打开页面，编辑内容会自动写回 HTML 文件。</p>
<ul>{rows}</ul>
<p style="color:#9898a8;font-size:13px">启动：<code>python3 scripts/serve.py</code></p>
</body></html>"""

    @app.get("/pages/<path:filename>")
    def serve_page(filename: str):
        if filename not in ALLOWED_PAGES:
            abort(404)
        return send_from_directory(PAGES_DIR, filename)

    @app.get("/assets/<path:filename>")
    def serve_asset(filename: str):
        return send_from_directory(ASSETS_DIR, filename)

    @app.post("/api/save/<path:filename>")
    def save_page(filename: str):
        if filename not in ALLOWED_PAGES:
            abort(403, description="Page not allowed")

        payload = request.get_json(silent=True) or {}
        html = payload.get("html", "")
        if not html or "<html" not in html.lower():
            return jsonify({"error": "Invalid HTML payload"}), 400

        target = PAGES_DIR / filename
        target.write_text(html, encoding="utf-8")
        return jsonify({"ok": True, "file": filename})

    return app


def main() -> None:
    if Flask is None:
        print("Error: flask not installed. Run: pip install -r scripts/requirements.txt", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="PM docs local server with auto-save")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    print(f"PM docs server: http://{args.host}:{args.port}/")
    print(f"Pages dir: {PAGES_DIR}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
