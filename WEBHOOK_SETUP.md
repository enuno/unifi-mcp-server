# WEBHOOK_SETUP

Operator runbook for webhook ingestion and event-bus handling.

## Purpose

Normalize UniFi event sources into a common internal format so downstream automation, audit consumers, and MCP callbacks can process them consistently.

## Event sources in scope

- controller webhook registration
- Protect alarm webhooks
- device events
- client or network events where supported
- optional fan-out through Redis pub/sub or an equivalent event bus

## Required inputs

- controller or Protect endpoint details
- webhook secret or signing key
- destination URL or local receiver configuration
- retry policy and timeout expectations
- approved event consumers

## Design rules

- verify every webhook using a shared secret or signature mechanism
- reject unsigned or malformed payloads
- normalize source-specific payloads into a single internal event envelope
- preserve raw payloads only when necessary for triage and only in controlled logs
- keep the receiver idempotent so replayed events do not cause duplicate side effects

## Deployment procedure

### 1. Register the webhook

1. Choose the controller and event class to register.
2. Register the callback endpoint.
3. Record the secret handling method.
4. Confirm the controller acknowledges the registration.

### 2. Validate the receiver

1. Send a known-good test event.
2. Verify signature validation passes.
3. Confirm the event is normalized into the internal schema.
4. Confirm the downstream consumer receives the normalized event.

### 3. Test fan-out behavior

1. Publish one event to the bus.
2. Confirm each subscribed consumer receives exactly one copy.
3. Confirm a slow consumer does not block the receiver path.

## Normalized event envelope

The normalized internal event should carry at minimum:

- event type
- source controller
- source site
- object identifier
- timestamp
- raw payload reference or digest
- verification status
- processing status

## Operational handling

### Retry and failure handling

- Retry transient upstream failures according to the controller’s expected behavior.
- Drop or quarantine invalid payloads after verification failure.
- Keep a dead-letter path for malformed or repeatedly failing events if the implementation provides one.

### Logging

Log:

- event source
- event type
- verification status
- processing status
- consumer delivery outcome

Do not log secrets, full webhook signing material, or sensitive payload content unless it is explicitly redacted.

## Verification checklist

- Webhook registration succeeds.
- Signature verification rejects tampered payloads.
- Normalized events preserve the required metadata.
- Duplicate deliveries do not produce duplicate side effects.
- Redis or the bus path recovers after a temporary outage.

## Common failure modes

- wrong secret or signature format
- controller webhook points at the wrong receiver URL
- normalization discards a field needed by downstream automation
- one bad consumer blocks the whole event chain
- event retries generate duplicate downstream actions

## Operator notes

- Treat webhook handling as an integration boundary, not a best-effort log stream.
- Prefer normalized events over source-specific parsing in downstream automations.
- Keep the receiver small and deterministic.

## Implementation

When `WEBHOOK_SECRET` is set, the server mounts `POST /webhooks/unifi`. After
signature verification, deduplication, and rate limiting, the receiver runs any
registered handlers and then publishes the normalized event to Redis pub/sub on
channel `unifi:webhooks:v1:events` if Redis is configured. Other replicas and
workers can subscribe to this channel to react to events without each receiving
the HTTP callback directly.

### Redis channel

- Channel: `unifi:webhooks:v1:events`
- Payload (JSON):

  ```json
  {
    "event_type": "device.online",
    "site_id": "default",
    "event_id": "evt-123456",
    "timestamp": "2026-10-27T12:34:56",
    "data": { "mac": "00:11:22:33:44:55", "name": "Access Point" },
    "origin": "<instance-id>"
  }
  ```

- Messages from the same instance are ignored by its own listener, so a process
does not react twice to an event it already handled locally.
- The publish runs as a background task, off the HTTP acknowledgement path: a
Redis that accepts connections but stops answering cannot delay the webhook
response, and the receiver still returns `200` after local handlers run.
- At most 1000 publishes may be in flight. Past that the fan-out drops events
with a warning rather than queueing without bound; local handlers still run.
- On shutdown the receiver waits up to 5 seconds for outstanding publishes,
then cancels them and logs how many never reached Redis.

### Verification

1. Register a webhook on the controller pointing at `https://<server>/webhooks/unifi`.
2. Trigger an event and confirm the receiver returns `200`.
3. With Redis configured, subscribe to `unifi:webhooks:v1:events` and confirm
the normalized event arrives.
4. Stop Redis, trigger an event, and confirm the receiver still returns `200`
while logging a warning.

## Status

Phase-5 documentation; Redis pub/sub fan-out implemented.
