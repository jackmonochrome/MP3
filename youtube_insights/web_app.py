import html
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from youtube_insights.fetchers import download_youtube_audio_mp3


ROOT_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = ROOT_DIR / "audio"


def _recent_downloads() -> list[Path]:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        [
            path
            for path in DOWNLOAD_DIR.glob("*.mp3")
            if not path.name.startswith("._")
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:15]


def _render_page(message: str = "", url_value: str = "") -> str:
    downloads_html = "\n".join(
        (
            f'<li><a href="/downloads/{html.escape(path.name)}">{html.escape(path.name)}</a> '
            f'({path.stat().st_size // 1024} KB)</li>'
        )
        for path in _recent_downloads()
    )
    if not downloads_html:
        downloads_html = "<li>No downloads yet.</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube MP3 Quick Grab</title>
  <style>
    :root {{
      --bg: #f5efe4;
      --card: #fffaf1;
      --ink: #1f1c18;
      --muted: #6f675c;
      --accent: #c84c2f;
      --accent-dark: #9e341c;
      --line: #e5d8c6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, #f8d8bf 0, transparent 24%),
        linear-gradient(135deg, #f5efe4, #efe2d0);
      color: var(--ink);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .card {{
      width: min(820px, 100%);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 24px 80px rgba(72, 47, 24, 0.12);
      padding: 28px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(2rem, 5vw, 3.4rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }}
    p {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 1.05rem;
    }}
    form {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      margin: 24px 0 16px;
    }}
    input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      font-size: 1rem;
      background: white;
    }}
    button {{
      border: 0;
      border-radius: 14px;
      padding: 16px 20px;
      font-size: 1rem;
      font-weight: 700;
      color: white;
      background: linear-gradient(180deg, var(--accent), var(--accent-dark));
      cursor: pointer;
    }}
    .message {{
      min-height: 24px;
      margin: 8px 0 22px;
      color: var(--accent-dark);
      font-weight: 700;
      word-break: break-word;
    }}
    .downloads {{
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }}
    ul {{
      margin: 10px 0 0;
      padding-left: 18px;
    }}
    li {{
      margin: 8px 0;
      color: var(--muted);
    }}
    a {{
      color: var(--ink);
    }}
    @media (max-width: 640px) {{
      form {{
        grid-template-columns: 1fr;
      }}
      button {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <main class="card">
    <h1>YouTube to MP3</h1>
    <p>Paste a YouTube link, click once, get an MP3 named after the video title.</p>
    <form method="post" action="/download">
      <input
        type="url"
        name="url"
        placeholder="https://www.youtube.com/watch?v=..."
        value="{html.escape(url_value)}"
        required
      >
      <button type="submit">Download MP3</button>
    </form>
    <div class="message">{html.escape(message)}</div>
    <section class="downloads">
      <h2>Recent Downloads</h2>
      <ul>{downloads_html}</ul>
    </section>
  </main>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._write_html(_render_page())
            return

        if parsed.path.startswith("/downloads/"):
            filename = Path(parsed.path.removeprefix("/downloads/")).name
            if filename.startswith("._"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = (DOWNLOAD_DIR / filename).resolve()
            if not target.exists() or target.parent != DOWNLOAD_DIR.resolve():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/download":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(raw_body)
        url = payload.get("url", [""])[0].strip()

        if not url:
            self._write_html(_render_page("Paste a YouTube URL first."))
            return

        try:
            mp3_path = download_youtube_audio_mp3(url, DOWNLOAD_DIR)
            message = f"Saved: {mp3_path.name}"
        except Exception as exc:
            message = f"Download failed: {exc}"

        self._write_html(_render_page(message=message, url_value=url))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    port = int(os.environ.get("PORT", "8123"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
