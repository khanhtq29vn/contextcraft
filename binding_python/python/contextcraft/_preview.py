"""Read-only, loopback-only preview of one analysis snapshot."""

from __future__ import annotations

import json
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from threading import Thread
from urllib.parse import parse_qs

from . import Config, FidelityLevel, RepositoryAnalysis


def serve_preview(
    analysis: RepositoryAnalysis,
    config: Config,
    *,
    port: int = 0,
    open_browser: bool = True,
) -> None:
    """Serve bundled assets and paginated snapshot data until interrupted.

    No repository paths are served directly. API requests require the session
    token carried in the browser URL fragment, which is not sent in HTTP URLs.
    """
    assets = files("contextcraft").joinpath("_static")
    index = analysis.index
    paths = {file_id: file.path.as_posix() for file_id, file in index.files.items()}
    scores = analysis.scores
    artifact = analysis.artifact
    selected = artifact.selected_tiers
    tiers = analysis.tiers.files
    ordered = sorted(paths, key=lambda file_id: (-scores[file_id], paths[file_id]))
    token = secrets.token_urlsafe(32)
    summary = {
        "repository": str(index.root),
        "files": len(paths),
        "loaded_files": len(analysis.repository.sources),
        "tokens": artifact.tokens,
        "budget": config.budget_tokens,
        "estimated": artifact.token_counts_estimated,
        "format": config.output_format.as_str(),
    }

    class PreviewHandler(BaseHTTPRequestHandler):
        server_version = "ContextCraft"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            # File paths and session details should not become access logs.
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self' "
                "https://cdn.jsdelivr.net/npm/marked@18.1.2/lib/marked.umd.js "
                "https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js "
                "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.12.0/highlight.min.js; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; connect-src 'self'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: object) -> None:
            self._send(
                200,
                json.dumps(value, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self) -> None:
            try:
                self._get()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _get(self) -> None:
            if self.headers.get("Host") != address or self.headers.get(
                "Origin"
            ) not in (
                None,
                origin,
            ):
                self._send(403, b"Forbidden", "text/plain")
                return

            path, _, query = self.path.partition("?")
            static_assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if path in static_assets:
                name, content_type = static_assets[path]
                self._send(200, assets.joinpath(name).read_bytes(), content_type)
                return

            if not path.startswith("/api/"):
                self._send(404, b"Not found", "text/plain")
                return
            if not secrets.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"),
                f"Bearer {token}".encode("ascii"),
            ):
                self._send(403, b"Forbidden", "text/plain")
                return
            if len(query) > 4096:
                self._send(414, b"Query too long", "text/plain")
                return

            try:
                params = parse_qs(query, max_num_fields=8)
                if path == "/api/summary":
                    self._json(summary)
                elif path == "/api/artifact":
                    self._send(
                        200,
                        artifact.content.encode("utf-8"),
                        "text/plain; charset=utf-8",
                    )
                elif path == "/api/files":
                    offset = int(params.get("offset", ["0"])[0])
                    limit = int(params.get("limit", ["100"])[0])
                    search = params.get("q", [""])[0]
                    selected_only = params.get("selected", ["1"])[0]
                    if (
                        offset < 0
                        or not 1 <= limit <= 200
                        or len(search) > 200
                        or selected_only not in ("0", "1")
                    ):
                        raise ValueError("Invalid file filters")
                    search = search.casefold()
                    items = []
                    total = 0
                    for file_id in ordered:
                        if search not in paths[file_id].casefold() or (
                            selected_only == "1"
                            and selected[file_id] == FidelityLevel.TREE
                        ):
                            continue
                        if offset <= total < offset + limit:
                            items.append(
                                {
                                    "id": file_id,
                                    "path": paths[file_id],
                                    "tier": selected[file_id].as_str(),
                                    "score": scores[file_id],
                                }
                            )
                        total += 1
                    self._json({"items": items, "total": total, "offset": offset})
                elif path.startswith("/api/files/"):
                    file_id = int(path.removeprefix("/api/files/"))
                    if file_id not in paths:
                        self._send(404, b"File not found", "text/plain")
                        return
                    levels = {
                        level.as_str(): tier
                        for level, tier in tiers[file_id].levels.items()
                    }
                    level = params.get("tier", [selected[file_id].as_str()])[0]
                    if level not in levels:
                        raise ValueError("Unavailable tier")
                    tier = levels[level]
                    self._json(
                        {
                            "path": paths[file_id],
                            "selected_tier": selected[file_id].as_str(),
                            "tier": level,
                            "levels": [
                                name
                                for name in ("TREE", "SIGS", "SKEL", "FULL")
                                if name in levels
                            ],
                            "score": scores[file_id],
                            "framed_tokens": tier.framed_tokens,
                            "content": tier.content,
                        }
                    )
                else:
                    self._send(404, b"Not found", "text/plain")
            except ValueError:
                self._send(400, b"Invalid request parameters", "text/plain")

    with ThreadingHTTPServer(("127.0.0.1", port), PreviewHandler) as server:
        address = f"127.0.0.1:{server.server_port}"
        origin = f"http://{address}"
        url = f"{origin}/#{token}"
        print(f"Preview: {url}\nPress Ctrl+C to stop.", file=sys.stderr, flush=True)
        if open_browser:

            def launch_browser() -> None:
                try:
                    if not webbrowser.open(url):
                        print("Open the preview URL in your browser.", file=sys.stderr)
                except (webbrowser.Error, OSError) as error:
                    print(f"Could not open browser: {error}", file=sys.stderr)

            # Text browsers can block until they exit; keep serving their requests.
            Thread(target=launch_browser, daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
