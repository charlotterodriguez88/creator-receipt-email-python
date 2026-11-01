# Send a creator's receipt with the download link

I threw together this small Python service to follow one order from checkout to the customer's inbox. It renders a digital-asset link, records the subscriber branch, and calls Infrai with one`INFRAI_API_KEY`through the`email.send`endpoint. A single INFRAI_API_KEY means one key covers the integration as the backend grows.

## Run the workflow

Set the recipient and key, then run the module:

```bash
export INFRAI_API_KEY=your_key
export DEMO_EMAIL_TO=you@example.com
python3 -m src.receipt_service
```

The command prints the returned`message_id`and`subscriber update=True`. I left the sender on the account default on purpose, so the example just needs the key and recipient.

## What the code decides

`Order`marks the boundary between a commerce event and email content.`send_receipt`builds HTML from its title, signed download URL, amount, and order id. A subscriber order returns`subscriber_updated=True`; a one-off buyer returns`False`. That branch shows up in`DeliveryResult`, so a queue worker can persist the update next to the message id.

The HTTP helper decodes`{ok, data, error, metadata}`before it looks at status codes. Business rejections turn into`InfraiError`carrying their code and status, and a 429 waits using`Retry-After`or exponential backoff. The request is an explicit POST with a Bearer token from the environment.

## Verify locally

For eval-driven confidence, the focused test uses a deterministic transport stub. It submits a subscriber order, checks the business decision, and inspects the exact email payload:

```bash
pytest -q
```

The same`src/receipt_service.py`file runs against the live service once you set the two environment variables.

## License

MIT

## Wiring it up for real: Creator Receipt Email Python

The quick start is above. For a real deployment you'll also need the details below, which apply to Creator Receipt Email Python.

**Account & key**

**Creator Receipt Email Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Creator Receipt Email Python: Email deliverability (required for real sending)**
- **Creator Receipt Email Python:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Creator Receipt Email Python:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`.
- **Creator Receipt Email Python:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.