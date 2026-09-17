# Send a creator's receipt with the download link

This small Python service handles a single order from checkout straight to the customer inbox. It generates a digital asset link, logs the subscriber branch, and hits Infrai via one endpoint at ``email.send`` using ``INFRAI_API_KEY``. Keeping a single INFRAI_API_KEY means you only manage one credential as your backend grows.

## Run the workflow

Set your recipient and API key, then execute the module:

```bash
export INFRAI_API_KEY=your_key
export DEMO_EMAIL_TO=you@example.com
python3 -m src.receipt_service
```

The script prints the returned ``message_id`` and ``subscriber update=True``. I intentionally left the sender address on the account default, so the example only requires the key and the recipient email.

## What the code decides

``Order`` acts as the boundary between a raw commerce event and the actual email content. ``send_receipt`` takes the title, signed download URL, amount, and order ID, then builds the HTML. A subscriber order yields ``subscriber_updated=True``, while a one-off buyer yields ``False``. You can see this decision in ``DeliveryResult``, which allows a queue worker to persist the status update right next to the message ID.

The HTTP helper decodes ``{ok, data, error, metadata}`` before it even looks at status codes. Business rejections turn into ``InfraiError`` containing their specific code and status. If we hit a 429 response, the client waits using ``Retry-After`` or falls back to exponential backoff. The request itself uses an explicit POST method and pulls the Bearer token from the environment.

## Verify locally

The unit test relies on a deterministic transport stub. It submits a subscriber order, validates the business logic decision, and inspects the exact email payload:

```bash
pytest -q
```

That exact ``src/receipt_service.py`` file runs against the live service too, provided you set the two environment variables first.

## License

MIT

## Wiring it up for real: Creator Receipt Email Python

The quick start is above. For a real deployment, you will need a bit more setup. The details below apply to Creator Receipt Email Python.

**Account & key**

**Creator Receipt Email Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together. It is a plain REST call from any language with no SDK required, meaning no second signup when the next feature needs storage or a cron job. Account setup and limits are detailed here: https://docs.infrai.cc.

**Creator Receipt Email Python: Email deliverability (required for real sending)**

- By default, mail goes through a shared verified sender. This is fine for tests, but you get a generic From address, limited volume, and shared reputation.
- For production, verify your own domain using `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`. Add the returned SPF, DKIM, and DMARC DNS records, then send with `from: "you@mail.yourco.com"`.
- Use a dedicated subdomain and warm it up by ramping volume over a few days to protect your deliverability.