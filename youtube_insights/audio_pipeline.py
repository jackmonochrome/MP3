import argparse
from pathlib import Path

from youtube_insights.fetchers import YtDlpUnavailableError, download_youtube_audio_mp3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a YouTube video's audio track as mp3."
    )
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output-dir", type=Path, default=Path("audio"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        mp3_path = download_youtube_audio_mp3(args.url, args.output_dir)
    except YtDlpUnavailableError as exc:
        raise SystemExit(str(exc)) from exc

    print(mp3_path)
    return 0
