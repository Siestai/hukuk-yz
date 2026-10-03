from hukuk_ingest.pipeline import FileResult
from hukuk_ingest.report import build_summary, render_markdown


def _result(path: str, **kwargs: object) -> FileResult:
    fields: dict[str, object] = {
        "sha256": "0" * 64,
        "size": 1,
        "ext": ".pdf",
        "detected_type": "pdf",
        "extension_mismatch": False,
        "status": "ok",
    }
    return FileResult(path=path, **{**fields, **kwargs})  # type: ignore[arg-type]


def _ocr(path: str, passes: list[int | None], ms: int, **kwargs: object) -> FileResult:
    return _result(path, quality={"ocr_pass": passes}, duration_ms=ms, **kwargs)


def test_summary_counts_ocr_files_pages_passes_and_seconds() -> None:
    summary = build_summary(
        [
            _ocr("a.pdf", [1, 2, 1], 1500),
            _ocr("b.pdf", [None, 3], 500),
            _result("c.pdf", quality={"chars": 1}),
        ],
        1.0,
    )
    assert summary["ocr"] | {"low_quality": [], "unavailable": []} == {
        "files": 2,
        "pages": 4,  # pages kept from the text layer are not OCR pages
        "passes": {"1": 2, "2": 1, "3": 1},
        "seconds": 2.0,
        "low_quality": [],
        "unavailable": [],
    }


def test_summary_lists_ocr_low_quality_and_unavailable_files() -> None:
    results = [
        _ocr("bad.pdf", [1], 10, status="needs_ocr", reason="ocr_low_quality"),
        _result(
            "none.pdf", status="needs_ocr", reason="no_text_layer", warnings=["ocr_unavailable"]
        ),
    ]
    summary = build_summary(results, 1.0)
    assert summary["ocr"]["low_quality"] == ["bad.pdf"]
    assert summary["ocr"]["unavailable"] == ["none.pdf"]


def test_summary_separates_readable_and_unreadable_legacy_docs() -> None:
    results = [
        _result("a.doc", detected_type="doc"),
        _result("b.pdf", detected_type="doc", status="unsupported", reason="encrypted_doc"),
        _result("c.pdf"),
    ]
    assert build_summary(results, 1.0)["legacy_doc"] == {
        "read": ["a.doc"],
        "unreadable": [{"path": "b.pdf", "status": "unsupported", "reason": "encrypted_doc"}],
    }


def test_markdown_renders_ocr_and_doc_sections_with_paths_only() -> None:
    results = [
        _ocr("bad.pdf", [1], 10, status="needs_ocr", reason="ocr_low_quality"),
        _result("a.doc", detected_type="doc"),
    ]
    markdown = render_markdown(build_summary(results, 1.0))
    assert "## OCR" in markdown
    assert "ocr_low_quality (1)" in markdown
    assert "- `bad.pdf`" in markdown
    assert "## Legacy .doc read (1)" in markdown
