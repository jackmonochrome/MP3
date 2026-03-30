import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

ROOT_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = ROOT_DIR / "audio"


def yt_dlp_base_cmd():
    yt_dlp = shutil.which("yt-dlp")
    if yt_dlp:
        return [yt_dlp]
    return ["python3", "-m", "yt_dlp"]


def run_cmd(cmd, cwd):
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        raise RuntimeError(stderr or stdout or str(exc)) from exc


def normalize_youtube_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url.strip()

    if "youtube.com" in host:
        params = parse_qs(parsed.query)
        video_id = (params.get("v") or [""])[0].strip()
        if video_id:
            return f"https://www.youtube.com/watch?{urlencode({'v': video_id})}"

    return url.strip()


def safe_filename(title: str, video_id: str, extension: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if not cleaned:
        cleaned = video_id
    cleaned = cleaned[:180].rstrip()
    return f"{cleaned} [{video_id}].{extension}"


def fetch_youtube_metadata(url: str):
    url = normalize_youtube_url(url)
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        cmd = yt_dlp_base_cmd() + [
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            "--extractor-args",
            "youtube:player_client=android",
            url,
        ]
        result = run_cmd(cmd, temp_dir)
    return json.loads(result.stdout)


def download_youtube_audio_mp3(url: str, output_dir: Path) -> Path:
    url = normalize_youtube_url(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    metadata = fetch_youtube_metadata(url)
    video_id = str(metadata.get("id") or "video")
    title = str(metadata.get("title") or video_id)
    final_path = output_dir / safe_filename(title, video_id, "mp3")

    if final_path.exists():
        return final_path

    cmd = yt_dlp_base_cmd() + [
        "--extractor-args",
        "youtube:player_client=android",
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--no-playlist",
        "-o",
        str(output_dir / safe_filename(title, video_id, "%(ext)s")),
        url,
    ]
    run_cmd(cmd, output_dir.parent)
    return final_path


def recent_downloads():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        [p for p in DOWNLOAD_DIR.glob("*.mp3") if not p.name.startswith("._")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:15]


def render_page(message: str = "", url_value: str = "") -> str:
    downloads_html = "\n".join(
        (
            f'<li><a href="/downloads/{html.escape(path.name)}">{html.escape(path.name)}</a> '
            f'({path.stat().st_size // 1024} KB)</li>'
        )
        for path in recent_downloads()
    ) or "<li>No downloads yet.</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube MP3 Quick Grab</title>
  <style>
    :root {{ --bg:#f5efe4; --card:#fffaf1; --ink:#1f1c18; --muted:#6f675c; --accent:#c84c2f; --accent-dark:#9e341c; --line:#e5d8c6; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Georgia, "Times New Roman", serif; background:radial-gradient(circle at top left, #f8d8bf 0, transparent 24%), linear-gradient(135deg, #f5efe4, #efe2d0); color:var(--ink); min-height:100vh; display:grid; place-items:center; padding:24px; }}
    .card {{ width:min(820px,100%); background:var(--card); border:1px solid var(--line); border-radius:24px; box-shadow:0 24px 80px rgba(72,47,24,.12); padding:28px; }}
    h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,3.4rem); line-height:.95; letter-spacing:-.04em; }}
    p {{ margin:0 0 18px; color:var(--muted); font-size:1.05rem; }}
    form {{ display:grid; grid-template-columns:1fr auto; gap:12px; margin:24px 0 16px; }}
    input {{ width:100%; border:1px solid var(--line); border-radius:14px; padding:16px 18px; font-size:1rem; background:white; }}
    button {{ border:0; border-radius:14px; padding:16px 20px; font-size:1rem; font-weight:700; color:white; background:linear-gradient(180deg, var(--accent), var(--accent-dark)); cursor:pointer; }}
    .message {{ min-height:24px; margin:8px 0 22px; color:var(--accent-dark); font-weight:700; word-break:break-word; }}
    .downloads {{ border-top:1px solid var(--line); padding-top:18px; }}
    ul {{ margin:10px 0 0; padding-left:18px; }}
    li {{ margin:8px 0; color:var(--muted); }}
    a {{ color:var(--ink); }}
    @media (max-width:640px) {{ form {{ grid-template-columns:1fr; }} button {{ width:100%; }} }}
  </style>
</head>
<body>
  <main class="card">
    <h1>YouTube to MP3</h1>
    <p>Paste a YouTube link, click once, choose where to save the MP3.</p>
    <form id="download-form" method="post" action="/download">
      <input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." value="{html.escape(url_value)}" required>
      <button type="submit">Download MP3</button>
    </form>
    <div id="message" class="message">{html.escape(message)}</div>
    <section class="downloads"><h2>Recent Downloads</h2><ul>{downloads_html}</ul></section>
  </main>
  <script>
    const form = document.getElementById('download-form');
    const message = document.getElementById('message');
    function setMessage(text) {{ message.textContent = text; }}
    function extractFilename(disposition) {{
      if (!disposition) return 'download.mp3';
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (utf8Match) return decodeURIComponent(utf8Match[1]);
      const asciiMatch = disposition.match(/filename="([^"]+)"/i);
      if (asciiMatch) return asciiMatch[1];
      return 'download.mp3';
    }}
    async function saveBlob(blob, filename) {{
      if (window.showSaveFilePicker) {{
        const handle = await window.showSaveFilePicker({{ suggestedName: filename, types: [{{ description: 'MP3 audio', accept: {{ 'audio/mpeg': ['.mp3'] }} }}] }});
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        return true;
      }}
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(blobUrl);
      return false;
    }}
    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const url = (new FormData(form).get('url') || '').trim();
      if (!url) {{ setMessage('Paste a YouTube URL first.'); return; }}
      setMessage('Preparing MP3, this can take a few seconds...');
      try {{
        const response = await fetch('/download', {{ method: 'POST', body: new URLSearchParams({{ url }}) }});
        if (!response.ok) throw new Error(await response.text() || 'Download failed');
        const filename = extractFilename(response.headers.get('Content-Disposition'));
        const blob = await response.blob();
        const usedPicker = await saveBlob(blob, filename);
        setMessage(usedPicker ? `Saved via file picker: ${filename}` : `Downloaded: ${filename}`);
      }} catch (error) {{
        setMessage(`Download failed: ${error.message}`);
      }}
    }});
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._write_html(render_page())
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
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(target.name)}")
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path != "/download":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(raw_body)
        url = payload.get("url", [""])[0].strip()
        if not url:
            self.send_error(HTTPStatus.BAD_REQUEST, "Paste a YouTube URL first.")
            return
        try:
            mp3_path = download_youtube_audio_mp3(url, DOWNLOAD_DIR)
            data = mp3_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(mp3_path.name)}")
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def log_message(self, format, *args):
        return

    def _write_html(self, body: str):
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
