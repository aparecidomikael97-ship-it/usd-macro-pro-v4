# AION Greeting Identity Separation — CI-only Draft V1

**Date:** 2026-10-09  
**Base:** main `5744b2b7b17c84331e6f27c569064993ff587782`  
**State:** code review only; no merge, no deploy, no runtime activation.

## Why

Before this patch `atlasquant_central_hub_ui._greeting_name` preferred
`access.display_name` over the authenticated session username and defaulted to
"Mikael" if no name existed. This is a presentation-level identity confusion:
an authorized delegated ADMIN might receive an owner-named greeting even
without independently attested HUMAN_OWNER identity.

The finding does **not** demonstrate escalation of privileges in the current
UI. It is still important not to use a greeting as an owner trust signal.

## Scoped correction

- For an already-authorized ADMIN session, derive the displayed greeting name
  strictly from `access.session.username`. Optional `display_name` labels,
  top-level `username`, or client-provided aliases never override it.
- Preserve the existing "Mikael" presentation alias only for exact session
  usernames `mikael` or `aparecidomikael`; this is a display convention,
  **not** owner authentication.
- Missing session username produces `Bom dia. AION ativo.` (or the appropriate
  afternoon/evening greeting), never an assumed identity.
- Escape the displayed name in HTML; keep the original clock, access check,
  navigation behavior, one-announcement-per-login semantics and disabled voice.
- `login_greeting` adds a single presentation-only `intro` field to avoid
  two divergent renderings between text and HTML; it returns no authority.
- Logged-out/non-admin sessions remain excluded by the existing access gate.

## Explicit trust boundary

Existing owner-stack Draft #1015 remains the reference for an **independently
verified HUMAN_OWNER assertion**, subject/issuer/credential binding and trusted
session permissions. This change does **not** integrate the external assertion
or convert ADMIN into HUMAN_OWNER. No new authority is granted for tools,
GitHub mutations, Windows install, release signing or anything else.

### Test cases

Regression tests exercise:
1. Delegated ADMIN with both top-level and session `display_name=Mikael` must
   still be greeted as the actual authenticated username.
2. ADMIN without a session username must see a neutral greeting, never Mikael.
3. Existing owner login aliases keep the same "Mikael" text.
4. Dangerous markup in the session username is HTML-escaped.
5. Greeting is not an owner assertion or authorization token.

Existing main regression suite additionally checks timezone Cuiabá, login and
logout, repeated rerender, voice fallback, AION navigation and other UI guards.

## Separate roadmap

- [#1117](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1117):
  master install GO/NO-GO plan.
- #1114 and #1116 stay separate Drafts with no physical certification;
  #1049 12/12 and #1087 16/16 physical evidence remain pending.
- Connecting a real conversational model, production persistence or an
  offline installed model requires its own reviewed feature and authorization.

**No owner-PC access, new keys, network/provider calls, billable resources,
production persistence, merge, build or installer.**
