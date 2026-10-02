from hukuk_models import HealthResponse


def test_health_response_serializes() -> None:
    assert HealthResponse(status="ok").model_dump() == {"status": "ok"}
