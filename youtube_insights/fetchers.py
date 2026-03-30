import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from youtube_insights.io_utils import load_comments
from youtube_insights.models import Transcript, TranscriptSegment, VideoInput


class YtDlpUnavailableError(RuntimeError):
    pass


class TranscriptUnavailableError(RuntimeError):
    pass


def _yt_dlp_base_cmd() -> List[str]:
    yt_dlp = shutil.which("yt-dlp")
    if yt_dlp:
        return [yt_dlp]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise YtDlpUnavailableError(
            "yt-dlp is not installed. Install it with `python3 -m pip install yt-dlp`."
        ) from exc
    return ["python3", "-m", "yt_dlp"]


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _safe_filename(title: str, video_id: str, extension: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if not cleaned:
        cleaned = video_id
    cleaned = cleaned[:180].rstrip()
    return f"{cleaned} [{video_id}].{extension}"


def _fetch_youtube_metadata(url: str) -> Dict[str, object]:
    yt_dlp_cmd = _yt_dlp_base_cmd()
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        cmd = yt_dlp_cmd + [
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            url,
        ]
        result = _run(cmd, temp_dir)
    return json.loads(result.stdout)


def download_youtube_audio_mp3(url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    yt_dlp_cmd = _yt_dlp_base_cmd()
    output_dir = output_dir.resolve()
    metadata = _fetch_youtube_metadata(url)
    video_id = str(metadata.get("id") or "video")
    title = str(metadata.get("title") or video_id)
    final_path = output_dir / _safe_filename(title, video_id, "mp3")

    if final_path.exists():
        return final_path

    cmd = yt_dlp_cmd + [
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
        str(output_dir / _safe_filename(title, video_id, "%(ext)s")),
        url,
    ]
    _run(cmd, output_dir.parent)

    mp3_files = sorted(
        [
            path
            for path in output_dir.glob("*.mp3")
            if not path.name.startswith("._")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not mp3_files:
        raise RuntimeError("yt-dlp finished but no mp3 file was created")
    return final_path if final_path.exists() else mp3_files[0]


def _fetch_transcript_via_api(video_id: str) -> Transcript:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise TranscriptUnavailableError(
            "No subtitles found and youtube-transcript-api is not installed."
        ) from exc

    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id, languages=["ru", "en"])
    segments = []
    text_parts = []
    for item in transcript:
        segments.append(
            TranscriptSegment(
                start=getattr(item, "start", None),
                end=(
                    getattr(item, "start", 0.0) + getattr(item, "duration", 0.0)
                    if getattr(item, "duration", None) is not None
                    else None
                ),
                text=item.text,
            )
        )
        text_parts.append(item.text)

    return Transcript(
        text="\n".join(text_parts).strip(),
        segments=segments,
    )


def fetch_from_youtube(url: str, comments_limit: int) -> VideoInput:
    yt_dlp_cmd = _yt_dlp_base_cmd()

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        info_cmd = yt_dlp_cmd + [
            "--skip-download",
            "--write-comments",
            "--extractor-args",
            "youtube:comment_sort=top",
            "--write-info-json",
            "-o",
            "%(id)s.%(ext)s",
            url,
        ]
        _run(info_cmd, temp_dir)

        info_files = sorted(temp_dir.glob("*.info.json"))
        if not info_files:
            raise RuntimeError("yt-dlp did not produce an info.json file")
        metadata: Dict[str, object] = json.loads(info_files[0].read_text(encoding="utf-8"))

        comments_raw = metadata.get("comments") or []
        comments_path = temp_dir / "comments.json"
        comments_path.write_text(json.dumps(comments_raw), encoding="utf-8")
        comments = load_comments(comments_path, comments_limit)

        transcript = Transcript(text="")
        video_id = str(metadata.get("id") or "")
        if video_id:
            try:
                transcript = _fetch_transcript_via_api(video_id)
            except Exception:
                transcript = Transcript(text="")

        return VideoInput(
            title=metadata.get("title"),
            url=url,
            transcript=transcript,
            comments=comments,
            metadata=metadata,
        )
