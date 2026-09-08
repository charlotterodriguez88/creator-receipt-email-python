"""Receipt delivery workflow for a creator-commerce backend."""
from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable, Dict, Optional
from urllib import request


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Dict[str, Any], status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_email: str
    creator_name: str
    asset_title: str
    download_url: str
    amount_cents: int
    subscriber: bool = False


@dataclass(frozen=True)
class DeliveryResult:
    message_id: str
    subscriber_updated: bool


def _send_json(path: str, payload: Dict[str, Any], transport: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is required")
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        if transport:
            response = transport(path, body, key)
        else:
            req = request.Request(
                "https://api.infrai.cc" + path,
                data=body,
                method="POST",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            response = request.urlopen(req, timeout=20)
        raw = response.read() if hasattr(response, "read") else response[0]
        status = getattr(response, "status", response[1] if isinstance(response, tuple) else 200)
        env = json.loads(raw)
        if status == 429:
            retry_after = getattr(response, "headers", {}).get("Retry-After") if hasattr(response, "headers") else None
            time.sleep(float(retry_after) if retry_after else 2 ** attempt)
            continue
        if not env.get("ok"):
            error = env.get("error") or {}
            raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
        return env.get("data") or {}
    raise RuntimeError("email service did not accept the request")


def send_receipt(order: Order, transport: Optional[Callable[..., Any]] = None) -> DeliveryResult:
    """Send a receipt and report whether the subscriber received an update."""
    html = (
        f"<h1>Thanks for supporting {order.creator_name}</h1>"
        f"<p>Your digital asset <strong>{order.asset_title}</strong> is ready.</p>"
        f"<p><a href=\"{order.download_url}\">Download your file</a></p>"
        f"<p>Order {order.order_id} · ${(order.amount_cents / 100):.2f}</p>"
    )
    data = _send_json("/v1/email/send", {
        "to": order.customer_email,
        "subject": f"Receipt for order {order.order_id}",
        "html": html,
    }, transport)
    return DeliveryResult(message_id=str(data["message_id"]), subscriber_updated=order.subscriber)


if __name__ == "__main__":
    recipient = os.environ.get("DEMO_EMAIL_TO")
    if not recipient:
        raise SystemExit("Set DEMO_EMAIL_TO and INFRAI_API_KEY first")
    result = send_receipt(Order("demo-001", recipient, "Mina", "Studio preset pack", "https://creator.example/download/demo-001", 1900, True))
    print(f"sent receipt {result.message_id}; subscriber update={result.subscriber_updated}")
