from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptSegment:
    start: Optional[float]
    end: Optional[float]
    text: str


@dataclass
class Transcript:
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)


@dataclass
class Comment:
    text: str
    author: Optional[str] = None
    likes: Optional[int] = None


@dataclass
class VideoInput:
    title: Optional[str]
    url: Optional[str]
    transcript: Transcript
    comments: List[Comment]
    metadata: Dict[str, Any] = field(default_factory=dict)
