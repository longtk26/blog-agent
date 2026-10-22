import logging

from src.configs.logger import ContextFilter, JsonFormatter, Redactor, request_id_ctx


def test_redactor_masks_known_secrets_and_auth_headers():
    redact = Redactor(["sk-live-abcdef"])
    text = redact('key=sk-live-abcdef Authorization: Bearer abc.def.ghi {"api-key": "devto123"} X-Agent-Key=local1')
    assert "sk-live-abcdef" not in text
    assert "abc.def.ghi" not in text
    assert "devto123" not in text
    assert "local1" not in text
    assert text.count("[REDACTED]") == 4


def test_json_formatter_includes_request_id_and_context():
    formatter = JsonFormatter(Redactor(["topsecret99"]))
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "calling with topsecret99", None, None)
    record.context = {"node": "plan"}
    token = request_id_ctx.set("req-1")
    try:
        ContextFilter().filter(record)
        line = formatter.format(record)
    finally:
        request_id_ctx.reset(token)
    assert '"request_id": "req-1"' in line
    assert '"node": "plan"' in line
    assert "topsecret99" not in line
