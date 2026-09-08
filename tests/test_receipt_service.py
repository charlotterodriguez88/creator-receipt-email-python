import json

from src.receipt_service import Order, send_receipt


class Reply:
    status = 200
    headers = {}

    def read(self):
        return json.dumps({"ok": True, "data": {"message_id": "msg_test_42"}, "metadata": {}}).encode()


def test_receipt_marks_subscriber_update_and_uses_order_fields(monkeypatch):
    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    calls = []

    def transport(path, body, key):
        calls.append((path, json.loads(body), key))
        return Reply()

    order = Order("ord-7", "fan@example.com", "Nora", "Video LUTs", "https://creator.example/d/ord-7", 1250, True)
    result = send_receipt(order, transport)
    assert result.message_id == "msg_test_42"
    assert result.subscriber_updated is True
    assert calls[0][0] == "/v1/email/send"
    assert calls[0][1]["to"] == "fan@example.com"
    assert "Video LUTs" in calls[0][1]["html"]
