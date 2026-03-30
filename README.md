# MP3

Tiny private YouTube-to-MP3 tool.

What it does:
- paste a YouTube URL into a small local web page
- click one button
- download an MP3 named after the video title

File names are saved like:

```text
Video Title [video_id].mp3
```

## Run locally

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the web app:

```bash
python3 run_web_app.py
```

Open:

```text
http://127.0.0.1:8123
```

## CLI

```bash
python3 extract_youtube_audio.py \
  --url "https://www.youtube.com/watch?v=..." \
  --output-dir audio
```

## Notes

- This repo is intended for private local use.
- Downloads are stored in `audio/`.
- The web UI also lists recent downloads.
