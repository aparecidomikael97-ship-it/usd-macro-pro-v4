# AION B2B Customer Portal Operations V1

Status: **staging / read-only / tenant-scoped**.

## Purpose

Expose customer-safe operational status for:

- managed automations;
- support tickets;
- ticket SLA posture.

This layer is presentation only. It cannot start, pause, reconfigure or disable an
automation. It cannot create, reply to, close or reprioritize a support ticket.

## Automation metadata

The portal may expose:

- automation ID;
- display name;
- state;
- last result;
- last run timestamp;
- next review timestamp.

Allowed states:

- ACTIVE;
- PAUSED;
- DEGRADED;
- PENDING;
- DISABLED.

Allowed last-result states:

- SUCCESS;
- FAILED;
- PARTIAL;
- UNKNOWN.

No schedule, credential, token, provider payload or executable command is exposed.

## Ticket metadata

The portal may expose:

- ticket ID;
- title;
- state;
- priority;
- SLA state;
- created timestamp;
- updated timestamp.

Allowed ticket states:

- OPEN;
- IN_PROGRESS;
- WAITING_CUSTOMER;
- RESOLVED;
- CLOSED.

Allowed priorities:

- LOW;
- MEDIUM;
- HIGH;
- CRITICAL.

Allowed SLA states:

- ON_TRACK;
- AT_RISK;
- BREACHED;
- NOT_APPLICABLE.

Message bodies, raw payloads, credentials and secrets are rejected.

## Derived counts

The read-only package may derive:

- total automations;
- degraded automations;
- open tickets;
- SLA-breached tickets;
- critical open tickets.

These counts never trigger an action automatically.

## Safety boundary

read_only=true.
automation_control_exposed=false.
ticket_write_exposed=false.
message_content_exposed=false.
automatic_automation_change=false.
automatic_ticket_change=false.
automatic_customer_contact=false.
provider_called=false.
production_mutation=false.
executes_action=false.
