from app.middleware.request_logging import resolve_request_id, sanitize_for_log


def test_plain_request_id_is_reused():
    assert resolve_request_id("abc-123_x.y") == "abc-123_x.y"


def test_unsafe_request_id_is_replaced():
    unsafe = "abc\nrequest_completed | status=200"

    assert resolve_request_id(unsafe) != unsafe
    assert len(resolve_request_id("x" * 200)) == 36


def test_control_characters_are_removed():
    assert "\n" not in sanitize_for_log("/api/farms\nfake")


def test_response_echoes_safe_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "trace-42"})

    assert response.headers["X-Request-ID"] == "trace-42"
