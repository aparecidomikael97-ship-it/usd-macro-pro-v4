# AtlasQuant Interface Finalization Lock — 2026-10-07

## Purpose

Freeze the approved information architecture for the AtlasQuant entry flow without changing AION Core authority or runtime behavior.

## Canonical entry flow

1. Login
2. ADMIN enters the Central root
3. Central shows exactly four primary ecosystem doors, in this order:
   - Trader
   - Negócios
   - Investimentos
   - AION
4. Selecting one door opens only that environment.
5. Each environment may expose its own internal complexity.
6. Returning to Central restores the four-door root.

## Simplicity contract

The Central root is intentionally **not** a dashboard of every capability.

It must not expose Trader modules, AION internal roles, Business modules, Investment modules, secondary navigation, market ranking, execution controls or internal diagnostics.

The product principle remains:

**Poderoso por dentro. Simples por fora.**

The current Trader contract contains 24 discoverable internal functions. That is acceptable only because those functions remain inside Trader and do not leak into the Central root.

## Current exact technical base

- AION Core V1 is formally frozen.
- immutable freeze target: `662eab4dc4f5bb009fa1ca89f87530df74d30ddf`
- current main base for this lock: `a6286cc0710309b66ff3c0bef5e23f4db1b723d1`
- Render auto-deploy is disabled and deployment remains separately authorized.
- no Core code is changed by this interface lock.
- no deploy, execution or Worker authority is introduced.

## Existing evidence on the base

The current main base already contains:

- four-door ADMIN Central contract;
- direct click routes for all four areas;
- real return-to-Central navigation;
- responsive browser coverage;
- login browser coverage;
- Trader internal navigation coverage;
- Negócios, Investimentos and AION environment rendering;
- AION's eight internal roles kept inside AION.

The finalization lock therefore adds regression protection, not a new product architecture.

## Non-negotiable regression rules

A future UI change is blocked if it:

- adds a fifth primary ecosystem door without an explicit product decision;
- puts inner workspace modules directly on Central;
- removes one of the four canonical areas;
- changes the canonical order;
- makes a private area inaccessible to an authorized ADMIN;
- prevents return to Central;
- leaks AION internal roles into the Central root;
- uses fake market data or fake readiness to fill visual space.

## Scope boundary

This interface work does not authorize:

- Core Freeze;
- merge;
- deploy;
- Global Worker arming/activation;
- trading execution;
- provider spending;
- external actions.

It is presentation/navigation governance only.
