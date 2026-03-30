import json
from pathlib import Path
from typing import Any, Dict, List

from youtube_insights.models import Comment, Transcript, TranscriptSegment


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_transcript(path: Path) -> Transcript:
    if path.suffix.lower() == ".txt":
        return Transcript(text=read_text(path))

    payload = read_json(path)
    if isinstance(payload, dict):
        text = str(payload.get("text", "")).strip()
        segments_raw = payload.get("segments", []) or []
        segments = [
            TranscriptSegment(
                start=item.get("start"),
                end=item.get("end"),
                text=str(item.get("text", "")).strip(),
            )
            for item in segments_raw
            if str(item.get("text", "")).strip()
        ]
        if not text and segments:
            text = "\n".join(segment.text for segment in segments)
        return Transcript(text=text, segments=segments)

    if isinstance(payload, list):
        segments = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            segment_text = str(item.get("text", "")).strip()
            if not segment_text:
                continue
            segments.append(
                TranscriptSegment(
                    start=item.get("start"),
                    end=item.get("end"),
                    text=segment_text,
                )
            )
        text = "\n".join(segment.text for segment in segments)
        return Transcript(text=text, segments=segments)

    raise ValueError(f"Unsupported transcript format in {path}")


def load_comments(path: Path, limit: int) -> List[Comment]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError("comments json must be a list")

    comments: List[Comment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        comments.append(
            Comment(
                text=text,
                author=item.get("author"),
                likes=item.get("likes"),
            )
        )
        if len(comments) >= limit:
            break
    return comments


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
