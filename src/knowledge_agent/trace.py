"""Append-only execution events and explicit run artifacts."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunRecorder:
    def __init__(self, directory: Path, run_id: str):
        self.directory = directory
        self.run_id = run_id
        self.sequence = 0
        directory.mkdir(parents=True, exist_ok=False)

    def write(self, name: str, value: Any) -> None:
        target = self.directory / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def append(self, name: str, value: Any) -> None:
        with (self.directory / name).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")

    def event(self, event_type: str, origin: str = "runtime", **payload: Any) -> None:
        self.sequence += 1
        self.append("trace.jsonl", {
            "run_id": self.run_id,
            "sequence": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "origin": origin,
            "payload": payload,
        })
