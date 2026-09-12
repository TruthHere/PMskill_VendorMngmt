#!/usr/bin/env python3
"""Local timeline server: edit in browser → Save writes project files directly.

Why: file:// HTML cannot write disk. This tiny localhost helper can.

Usage:
  python3 serve_timeline.py --project-root "/path/to/project" --open

Then edit → 保存. Next open (file or this server) shows the saved state.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from apply_timeline_edits import apply_payload  # noqa: E402
from render_timeline import default_timeline_paths, write_timeline  # noqa: E402

LIVE_MARK = '<script>window.TIMELINE_LIVE_SAVE=true;</script>'


def _ensure_timeline(root: Path) -> Path:
    human, _skill = default_timeline_paths(root)
    if not human.is_file():
        write_timeline(root)
    if not human.is_file():
        raise FileNotFoundError(f"timeline HTML missing: {human}")
    return human


def _write_launcher(root: Path, port: int) -> Path:
    """Double-clickable macOS/Linux launcher in 进度计划 folder."""
    human, _ = default_timeline_paths(root)
    folder = human.parent
    folder.mkdir(parents=True, exist_ok=True)
    launcher = folder / "打开时间线（可直接保存）.command"
    py = sys.executable
    script = Path(__file__).resolve()
    body = f"""#!/bin/bash
cd "{root}"
exec "{py}" "{script}" --project-root "{root}" --port {port} --open
"""
    launcher.write_text(body, encoding="utf-8")
    try:
        os.chmod(launcher, 0o755)
    except OSError:
        pass
    return launcher


class TimelineHandler(BaseHTTPRequestHandler):
    project_root: Path = Path(".")
    port: int = 8765

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html", "/timeline"}:
            try:
                html_path = _ensure_timeline(self.project_root)
                text = html_path.read_text(encoding="utf-8")
                if "TIMELINE_LIVE_SAVE" not in text:
                    if "</head>" in text:
                        text = text.replace("</head>", LIVE_MARK + "\n</head>", 1)
                    else:
                        text = LIVE_MARK + text
                self._send(200, text.encode("utf-8"), "text/html; charset=utf-8")
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/api/ping":
            self._send_json(
                200,
                {
                    "ok": True,
                    "live_save": True,
                    "project_root": str(self.project_root),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/save":
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"ok": False, "error": f"invalid JSON: {exc}"})
            return
        try:
            result = apply_payload(self.project_root, payload, refresh_cards=False)
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return
        code = 200 if result.get("ok") else 400
        self._send_json(code, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve critical-nodes timeline with one-click Save to disk"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the timeline in your default browser",
    )
    parser.add_argument(
        "--write-launcher",
        action="store_true",
        default=True,
        help="Write/update 打开时间线（可直接保存）.command (default on)",
    )
    parser.add_argument(
        "--no-write-launcher",
        action="store_true",
        help="Do not write the double-click launcher",
    )
    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve()
    if not (root / ".skill").is_dir():
        print(
            json.dumps(
                {"ok": False, "error": f"not a project root (missing .skill): {root}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    _ensure_timeline(root)

    TimelineHandler.project_root = root
    ThreadingHTTPServer.allow_reuse_address = True
    port = args.port
    server = None
    last_err: OSError | None = None
    for candidate in [port, *range(port + 1, port + 20)]:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), TimelineHandler)
            port = candidate
            break
        except OSError as exc:
            last_err = exc
            continue
    if server is None:
        print(
            json.dumps(
                {"ok": False, "error": f"no free port near {args.port}: {last_err}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    TimelineHandler.port = port
    launcher = None
    if args.write_launcher and not args.no_write_launcher:
        launcher = _write_launcher(root, port)

    url = f"http://127.0.0.1:{port}/"
    info = {
        "ok": True,
        "url": url,
        "project_root": str(root),
        "hint": "浏览器里改完点「保存」即可写回项目；关掉本窗口即停止服务",
    }
    if launcher:
        info["launcher"] = str(launcher)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
