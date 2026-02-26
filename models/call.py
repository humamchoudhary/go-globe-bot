from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


@dataclass
class Call:
    call_id: str
    status: str = "ended"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    audio: str = ""
    recording_url: str = ""
    transcription: List[Dict[str, Any]] = field(default_factory=list)
    userdata: Dict[str, Any] = field(default_factory=dict)
    call_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Call":
        data = data or {}
        return cls(
            call_id=data.get("call_id", ""),
            status=data.get("status", "ended"),
            started_at=_parse_datetime(data.get("started_at")),
            ended_at=_parse_datetime(data.get("ended_at")),
            audio=data.get("audio", "") or "",
            recording_url=data.get("recording_url", "") or "",
            transcription=data.get("transcription") or [],
            userdata=data.get("userdata") or {},
            call_metadata=data.get("call_metadata") or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "audio": self.audio,
            "recording_url": self.recording_url,
            "transcription": self.transcription,
            "userdata": self.userdata,
            "call_metadata": self.call_metadata,
        }