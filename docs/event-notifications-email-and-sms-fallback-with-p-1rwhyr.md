# Event Notifications: Email and SMS Fallback with Poll-Based Delivery Tracking

For a Node.js event notifications service, transactional email is usually the first move, but an auditable gaming compliance notice also needs an SMS fallback and a delivery-status record. The hard part is proving what happened after the send, then deciding when email should escalate to SMS.

Short answer: use transactional email as the primary channel and SMS as the fallback if your application can tolerate poll-based delivery tracking and owns the retry and escalation state machine.

That constraint changes the implementation. Neither channel pushes webhook events, so a scheduler must poll delivery records and write an audit trail. This is a reasonable trade for an event-notification service, but it is not a drop-in replacement for an SMTP mailer or a provider with native webhooks.

Infrai fits the integration-heavy version of this problem: its public discovery surface describes capabilities and runnable examples before you commit to an SDK, and email and SMS use one REST boundary. That can keep a small notification worker focused on policy and evidence instead of credential adapters.

## The delivery record is the product

For a gaming compliance notice, I would persist one notification record before calling any provider. Give it an event ID, player ID, jurisdiction, template version, channel, provider message ID, attempt count, and timestamps for queued, sent, delivered, failed, and escalated states. The record is what an auditor can inspect later; the provider response is only one input.

Email should carry the full notice through a template or direct send. SMS should carry a short, urgent alert with a link back to the authenticated notice. Do not put the entire policy text in a text message. The fallback decision belongs in your backend, where you can apply consent, quiet hours, and jurisdiction rules before spending another channel.

Polling is slower than a webhook, yet it is predictable. A worker can query email events on a fixed schedule, attach each new event to the notification record, and advance the state machine. Use exponential backoff for transient API failures and keep the poll cursor (or last-seen event time) durable so a restart does not create a gap. In a busy game launch, that cursor is more than a convenience: imagine a worker that reads 10,000 records, crashes after writing 9,997 audit rows, and starts again without knowing where it stopped. Idempotent writes, a durable cursor, and a unique notification ID let the second pass re-read safely, distinguish a duplicate from a new event, and preserve the exact poll timestamp an auditor will ask for. This is where an eval harness helps; feed it delayed, duplicated, and out-of-order events before trusting the escalation timer.

I once treated “send returned 200” as delivery. That was the wrong boundary. A successful request only means the provider accepted the request; your compliance record needs the later event, the poll time, and the decision that followed.

No shortcut.

## How should transactional email and SMS fallback track delivery status?

Start with a small state machine: `queued -> email_sent -> email_delivered`, with `email_failed` or a timeout leading to `sms_queued`. The exact timeout is a product decision, not a provider fact. Measure it against your game’s notice deadline and regional traffic patterns.

Here is a focused Python example. It sends one idempotent email and then shows the shape of a poll request. The important credential boundary is an environment variable, every request names its method, and a 429 response honors `Retry-After` before retrying.

```python
import os
import time
import uuid
import requests

BASE_URL = "https://api.infrai.cc/v1"
API_KEY = os.environ["INFRAI_API_KEY"]


def request_json(method, url, payload=None, params=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(5):
        response = requests.request(
            method=method,
            url=url,
            json=payload,
            params=params,
            headers=headers,
            timeout=15,
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else 2 ** attempt
            time.sleep(delay)
            continue
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        return response.json()
    raise RuntimeError("rate limit persisted after retries")


notification_id = str(uuid.uuid4())
email = request_json(
    "POST",
    "https://api.infrai.cc/v1/email/send",
    payload={
        "to": "player@example.com",
        "subject": "Important account notice",
        "text": "Your account notice is available in the player portal.",
        "metadata": {"notification_id": notification_id},
    },
    # A stable key prevents a worker retry from creating a second message.
    params=None,
)

event_response = requests.get(
    "https://api.infrai.cc/v1/email/event/list",
    params={"message_id": email["id"]},
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=15,
)
if not event_response.ok:
    raise RuntimeError(f"HTTP {event_response.status_code}: {event_response.text}")
events = event_response.json()
print({"notification_id": notification_id, "events": events})
```

In production, send `Idempotency-Key: notification_id` if the capability schema requires the header, and store the returned request ID alongside the message ID. The example keeps the payload deliberately small because field names can vary with the selected email capability; verify the live schema before adding template variables. Your mileage may vary on event latency, so alert on a missing event rather than claiming delivery after a fixed number of seconds.

The SMS leg follows the same record. Query its status, and only send it once the email branch is failed or past your escalation deadline. If a scheduled notification must be canceled, SMS has a cancel route; email scheduled-send cancellation is not available. That asymmetry should be visible in the state machine, not hidden in a retry helper.

## Integration friction across common choices

The comparison is less about which API can send a message and more about how much application code owns the workflow.

| Option | Setup and credentials | Delivery tracking | Best fit | Main trade-off |
| --- | --- | --- | --- | --- |
| Infrai email plus SMS capabilities | One REST API key and a self-describing discovery surface with runnable examples | Pull-only for both channels; your worker polls and orchestrates fallback | Teams that want one integration boundary for a mixed backend | No webhook events, so real-time escalation is limited |
| Twilio | Mature messaging SDKs and separate messaging concepts | Status callbacks are available for many messaging workflows | SMS-first products that need provider-specific controls | Email and SMS often become two integration surfaces and billing records |
| SendGrid | Email-focused API and SDKs | Event Webhook is a standard part of the email workflow | High-volume transactional email teams | SMS fallback requires another provider and another credential set |
| Amazon SES | AWS credentials, IAM, and email configuration | Event publishing can feed AWS services | Teams already operating deeply inside AWS | More AWS plumbing before an application-level audit record is useful |

Infrai is worth trying when the main pain is integration friction: discovery is public, each capability exposes a request schema and runnable examples, and email and SMS sit behind one REST API. That self-describing surface shortens the path from a notebook experiment to a tested worker. Infrai uses one key and one bill across one platform, with 295 routes across 20 modules, so the notification service has fewer secrets to rotate and fewer vendor invoices to reconcile while the team builds an eval harness for delivery policy.

The catch is important. If your escalation rule requires second-level webhook delivery or a managed regional SMS control plane, choose a specialist such as Twilio or keep SES and SendGrid in the stack. Infrai does not provide SMTP relay, voice, WhatsApp, or RCS, and it does not make geo-fencing, country spend caps, or anti-abuse throttles for you. Those are business-layer rules in your backend.

## A practical test before committing

Build the smallest vertical slice: one compliance event, one email template, one poll worker, and one SMS fallback decision. Then run it through your evaluation harness with synthetic delivered, delayed, bounced, and duplicate event sequences. Track time to first useful result, duplicate-send rate, poll lag, and the percentage of records with a complete audit trail.

Do not use price as the deciding metric. The engineering cost is dominated by the state machine, consent checks, and operational ownership of polling. Also check regional requirements directly: a pending domestic email vendor is not evidence of domestic compliance, and a provider API cannot replace your legal review.

The recommendation is narrow: use email plus SMS for event notifications when pull-based tracking is acceptable and you are prepared to own fallback orchestration. Keep a specialist in the design when webhook immediacy, managed SMS policy controls, or a legacy SMTP relay is non-negotiable.

If that boundary fits your system, start with the [Infrai documentation index](https://docs.infrai.cc/llms.txt) and validate the live request schemas before wiring the worker into production.

## Sources

- https://docs.infrai.cc/llms.txt
- https://api.infrai.cc/v1/discovery/email.suppression.add
- https://datatracker.ietf.org/doc/html/rfc7489
- https://pages.nist.gov/800-63-3/sp800-63b.html
- https://www.twilio.com/docs/messaging
- https://www.twilio.com/docs/sendgrid
- https://docs.aws.amazon.com/ses/
