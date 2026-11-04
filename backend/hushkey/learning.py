"""One reviewed utterance at a time; predictions are never training labels by default."""
from __future__ import annotations

import json
from time import monotonic
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator

from .preprocess.pipeline import RawFrame, Sample, resample_indices


class MotionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: FiniteFloat
    callback_uptime: FiniteFloat
    acceleration: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    rotation: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    attitude: tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class CaptureMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    motion_status: str = Field(max_length=200)
    motion: list[MotionPoint] = Field(default_factory=list, max_length=4000)


class Confirmation(BaseModel):
    capture_id: UUID
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter the words you actually mouthed.")
        return value


@dataclass
class PendingExample:
    capture_id: str
    sample: Sample
    metadata: dict
    expires_at: float

    @classmethod
    def create(cls, sample: Sample, frames: list[RawFrame], capture: CaptureMetadata):
        return cls(str(uuid4()), sample, {
            **capture.model_dump(mode="json"),
            "schema_version": 1,
            "condition": "silent",
            "camera_timestamps": [f.t for f in frames],
            "camera_callback_uptimes": [f.callback_uptime for f in frames],
            "model_frame_source_indices": resample_indices([f.t for f in frames]),
            "clock_alignment": "unverified; native timestamps and host callback uptimes retained",
        }, monotonic() + 600)

    def save(self, directory: Path, confirmation: Confirmation) -> str:
        if str(confirmation.capture_id) != self.capture_id or monotonic() > self.expires_at:
            raise ValueError("This capture is no longer available. Record it again.")
        name = f"reviewed-{self.capture_id}"
        directory.mkdir(parents=True, exist_ok=True)
        self.sample.save(directory / f"{name}.npz", text=confirmation.text)
        metadata = {**self.metadata, "capture_id": self.capture_id,
                    "text": confirmation.text, "label_source": "user_confirmed"}
        (directory / f"{name}.json").write_text(json.dumps(metadata, indent=2))
        row = {"path": f"{name}.npz", "text": confirmation.text,
               "frames": len(self.sample.rois), "session_id": self.metadata["session_id"],
               "metadata": f"{name}.json", "label_source": "user_confirmed"}
        with (directory / "manifest.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        return f"{name}.npz"
