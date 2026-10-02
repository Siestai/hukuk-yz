"""Content-based type detection and text extraction (task 03). No DB, no app dependency."""

from hukuk_ingest.detect import DetectedType, Detection, detect

__all__ = ["DetectedType", "Detection", "detect"]
