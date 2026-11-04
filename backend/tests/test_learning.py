"""Exercise real preprocessing, websocket lifecycle, persistence and training-data loading."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hushkey.config import Paths
from hushkey.data import UtteranceDataset, read_manifest
from hushkey.engine import Engine, EngineConfig
from hushkey.preprocess.pipeline import Sample
from hushkey.server import create_app
from .synth import wire_frames


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("HUSHKEY_HOME", str(tmp_path))
    engine = Engine(EngineConfig(tiny=True, beam_size=1, device="cpu"))
    return TestClient(create_app(engine)), Paths().ensure()


def capture(ws, *, review=True, motion=True):
    session_id = str(uuid4())
    ws.send_json({"type": "start", "partials": False, "review_capture": review})
    for frame in wire_frames(0.6, fps=25):
        ws.send_json({**frame, "callback_uptime": frame["t"] + 0.01})
    ws.send_json({"type": "stop", "capture": {
        "session_id": session_id, "motion_status": "Streaming" if motion else "Unavailable",
        "motion": [{"t": 100.1, "callback_uptime": 100.11,
                    "acceleration": [0.1, 0.2, 0.3], "rotation": [0.4, 0.5, 0.6],
                    "attitude": [0.7, 0.8, 0.9]}] if motion else [],
    }})
    result = ws.receive_json()
    assert result["type"] == "final", result
    return result, session_id


def test_only_confirmed_text_is_persisted_with_paired_sensor_metadata(setup):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        result, session_id = capture(ws)
        assert list(paths.enrollment.iterdir()) == []
        confirmation = {"type": "confirm_capture", "capture_id": result["capture_id"],
                        "text": "  send the corrected sentence  "}
        ws.send_json(confirmation)
        saved = ws.receive_json()
        assert saved["type"] == "capture_saved", saved
        ws.send_json(confirmation)
        assert ws.receive_json() == saved
    manifest = paths.enrollment / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["text"] == "send the corrected sentence"
    assert rows[0]["session_id"] == session_id
    metadata = json.loads((paths.enrollment / rows[0]["metadata"]).read_text())
    assert metadata["motion"][0]["acceleration"] == [0.1, 0.2, 0.3]
    assert metadata["camera_callback_uptimes"][0] == 100.01
    assert metadata["camera_timestamps"][0] == 100
    assert metadata["model_frame_source_indices"] == list(range(15))
    assert metadata["label_source"] == "user_confirmed"
    sample, text = Sample.load(paths.enrollment / rows[0]["path"])
    assert text == rows[0]["text"]
    assert sample.rois.shape == (15, 96, 96)
    dataset = UtteranceDataset(read_manifest(manifest))
    assert len(dataset) == 1
    assert dataset[0]["text"].lower() == text


def test_discard_and_next_capture_cannot_save_stale_data(setup):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        first, _ = capture(ws)
        ws.send_json({"type": "discard_capture"})
        ws.send_json({"type": "confirm_capture", "capture_id": first["capture_id"], "text": "wrong"})
        assert ws.receive_json()["type"] == "review_error"
        second, _ = capture(ws)
        third, _ = capture(ws, motion=False)
        ws.send_json({"type": "confirm_capture", "capture_id": second["capture_id"], "text": "stale"})
        assert ws.receive_json()["type"] == "review_error"
        ws.send_json({"type": "confirm_capture", "capture_id": third["capture_id"], "text": "camera only"})
        saved = ws.receive_json()
        assert saved["type"] == "capture_saved"
    row = json.loads((paths.enrollment / "manifest.jsonl").read_text())
    metadata = json.loads((paths.enrollment / row["metadata"]).read_text())
    assert metadata["motion"] == []
    assert row["text"] == "camera only"


def test_plain_dictation_and_cancel_never_enroll(setup):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        result, _ = capture(ws, review=False)
        assert "capture_id" not in result
        pending, _ = capture(ws)
        ws.send_json({"type": "cancel"})
        ws.send_json({"type": "confirm_capture", "capture_id": pending["capture_id"], "text": "cancelled"})
        assert ws.receive_json()["type"] == "review_error"
    assert list(paths.enrollment.iterdir()) == []


def test_bad_confirmation_is_rejected_without_losing_reviewable_capture(setup):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        result, _ = capture(ws)
        for text in ["   ", "x" * 1001]:
            ws.send_json({"type": "confirm_capture", "capture_id": result["capture_id"], "text": text})
            assert ws.receive_json()["type"] == "review_error"
        assert list(paths.enrollment.iterdir()) == []
        ws.send_json({"type": "confirm_capture", "capture_id": result["capture_id"], "text": "confirmed"})
        assert ws.receive_json()["type"] == "capture_saved"


def test_expired_capture_cannot_be_confirmed(setup, monkeypatch):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        result, _ = capture(ws)
        # Clock is the only boundary replaced; preprocessing and storage stay real.
        monkeypatch.setattr("hushkey.learning.monotonic", lambda: float("inf"))
        ws.send_json({"type": "confirm_capture", "capture_id": result["capture_id"], "text": "too late"})
        assert ws.receive_json()["type"] == "review_error"
    assert list(paths.enrollment.iterdir()) == []


def test_disconnect_drops_unsaved_capture(setup):
    client, paths = setup
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        result, _ = capture(ws)
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_json()
        ws.send_json({"type": "confirm_capture", "capture_id": result["capture_id"], "text": "old connection"})
        assert ws.receive_json()["type"] == "review_error"
    assert list(paths.enrollment.iterdir()) == []
