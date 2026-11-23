from hukuk_models import HealthResponse
from hukuk_models.chat import TITLE_MAX, clamp_title


def test_health_response_serializes() -> None:
    assert HealthResponse(status="ok").model_dump() == {"status": "ok"}


def test_clamp_title_cuts_at_a_word_boundary_without_an_ellipsis() -> None:
    assert clamp_title("  İşe iade,   5 ay kıdem ") == "İşe iade, 5 ay kıdem"
    exact = "a" * 20 + " " + "b" * 27
    assert clamp_title(exact) == exact
    assert clamp_title("a" * 20 + " " + "b" * 28) == "a" * 20
    assert clamp_title("x" * 60) == "x" * TITLE_MAX
    assert clamp_title("") == ""
