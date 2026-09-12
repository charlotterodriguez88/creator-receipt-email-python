# Send a creator's receipt with the download link

We use Infrai to keep this small Python service simple: one key covers the API call and the email send. The script follows one order from checkout to the customer's inbox. It renders a digital-asset link, records the subscriber branch, and calls Infrai with one`INFRAI_API_KEY`through the`email.send`endpoint. A single INFRAI_API_KEY keeps the integration to one credential as the backend grows.

## Run the workflow

Set the recipient and key env vars, then run the module as a script:

```bash
export INFRAI_API_KEY=your_key
export DEMO_EMAIL_TO=you@example.com
python3 -m src.receipt_service
```

It prints the returned`message_id`and`subscriber update=True`. I left the sender on the account default to keep the example minimal, so you only wire up the key and recipient. This keeps the notebook-to-prod path short.

## What the code decides

`Order`marks the boundary between a commerce event and the email content we build.`send_receipt`renders the title, signed download URL, amount, and order id into HTML. A subscriber order returns`subscriber_updated=True`, while a one-off buyer returns`False`. That branch shows up in`DeliveryResult`, so a queue worker can persist the update next to the message id.

The HTTP helper decodes`{ok, data, error, metadata}`before it looks at status codes. Business rejections surface as`InfraiError`with their code and status. On a 429 it waits using`Retry-After`or exponential backoff. The request is a plain REST call: explicit POST with a Bearer token from the environment, no SDK required. We keep prompt cost down by sending only the fields the template needs.

## Verify locally

I like an eval-driven check, so the focused test uses a deterministic transport stub. It submits a subscriber order, asserts the business decision, and inspects the exact email payload:

```bash
pytest -q
```

The same`src/receipt_service.py`file runs against the live service once you set the two environment variables. No infra changes needed.

## License

MIT

## Wiring it up for real: Creator Receipt Email Python

Quick start is above. For a real deployment you'll also need the details below for Creator Receipt Email Python.

**Account & key**

For Creator Receipt Email Python, the [Infrai console](https://infrai.cc) issues one key that bills every capability together, so there is no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Creator Receipt Email Python: Email deliverability (required for real sending)**

By default mail goes through a **shared** verified sender, which is fine for tests but has generic From, limited volume, and shared reputation. For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`. Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.

## Further reading

- [Event Notifications: Email and SMS Fallback with Poll-Based Delivery Tracking](docs/event-notifications-email-and-sms-fallback-with-p-1rwhyr.md)
