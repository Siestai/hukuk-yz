"""Detection of a document's type and reference fields from its extracted text (task 13a).

`classify` runs the rules, and only for the fields they leave empty asks a `Detector` (a language
model behind an interface). The result is a set of suggestions; nothing here writes a record."""

import logging
import time
from dataclasses import dataclass, field

from hukuk_ingest.classify import rules
from hukuk_ingest.classify.evidence import FIELDS, Suggestion, Suggestions
from hukuk_ingest.classify.llm import (
    Detector,
    DetectorError,
    DetectRequest,
    excerpt,
    validate,
)

logger = logging.getLogger("hukuk_ingest.classify")

# The rules in the order they are tried; the first that finds anything wins. A decision is
# tried before a circular: a decision cites circulars.
_TEXT_RULES = (
    rules.kanun,
    rules.karar,
    rules.genelge,
    rules.ic_emri,
    rules.regulation,
    rules.genel_yazi,
)
# What the rules are expected to find in every document; the model is asked only when one of
# these is missing, for all the fields that are missing.
_ASK_WHEN_MISSING = ("doc_type", "doc_date", "official_ref", "title")

__all__ = ["Classification", "Detector", "Suggestion", "Suggestions", "classify"]


@dataclass
class Classification:
    suggestions: Suggestions = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def rule_suggestions(text: str, detected_type: str) -> Suggestions:
    if found := rules.spreadsheet(detected_type):
        return found
    for rule in _TEXT_RULES:
        if found := rule(text):
            return found
    return {}


def classify(
    text: str, detected_type: str, file_name: str, detector: Detector | None = None
) -> Classification:
    """Suggestions for one document. A failing detector is a warning (`detector_failed`), not an
    error: the rule suggestions are kept."""
    result = Classification(rule_suggestions(text, detected_type))
    wanted = tuple(name for name in FIELDS if name not in result.suggestions)
    if detector is None or not text.strip() or not any(n in wanted for n in _ASK_WHEN_MISSING):
        return result
    request = DetectRequest(file_name, excerpt(text), wanted)
    started = time.perf_counter()
    try:
        answer = detector.detect(request)
    except DetectorError as exc:
        logger.warning("detector failed after %.1fs: %s", time.perf_counter() - started, exc)
        result.warnings.append("detector_failed")
        return result
    found = validate(answer.answer, text, wanted)
    logger.info(
        "detector %s: %d input / %d output tokens, %d ms, fields %s",
        answer.model,
        answer.input_tokens,
        answer.output_tokens,
        round((time.perf_counter() - started) * 1000),
        sorted(found),
    )
    result.suggestions.update(found)
    return result
