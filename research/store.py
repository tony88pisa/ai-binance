"""
Research store — atomic read/write of ResearchState to JSON.

Uses write-to-tmp + rename pattern for crash safety.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from research.types import ResearchState

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "user_data" / "research_state.json"


def write_state(state: ResearchState, path: Path = DEFAULT_STATE_PATH) -> bool:
    """Write research state atomically. Returns True on success."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = state.to_json()

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=".research_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            # Atomic rename (on Windows, need to remove target first)
            if path.exists():
                path.unlink()
            os.rename(tmp_path, str(path))
            return True
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    except Exception as e:
        logger.error(f"Failed to write research state: {e}")
        return False


def read_state(path: Path = DEFAULT_STATE_PATH) -> ResearchState | None:
    """Read research state from disk. Returns None if unavailable."""
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ResearchState(**data)
    except Exception as e:
        logger.error(f"Failed to read research state: {e}")
        return None
