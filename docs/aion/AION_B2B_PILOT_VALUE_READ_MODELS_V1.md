# AION B2B Pilot Value Read Models V1

Status: **staging / read-only projections**.

## Admin projection

The Admin cockpit may see:

- value state and review recommendation;
- health score;
- value trend;
- quick-win completion and attainment;
- observed savings and ROI;
- customer fee/value ratio/net value;
- AtlasQuant delivery cost and gross margin;
- retention risk and low-value alert;
- review reasons.

The Admin projection is read-only and exposes no renewal, expansion, billing or
customer-contact control.

## Customer projection

The customer-safe projection may see:

- pilot ID;
- value state;
- health score;
- value trend;
- quick-win progress;
- observed savings;
- observed ROI;
- customer fee;
- customer value-to-fee ratio;
- net customer value;
- payback coverage.

It deliberately omits:

- AtlasQuant delivery cost;
- gross margin;
- retention-risk score/label;
- internal recommendation;
- internal review reasons;
- owner identity;
- evidence sources;
- business-action controls.

## Portal boundary

The customer-safe projection is prepared but is not automatically wired to the
Portal do Cliente. A separate explicit pilot-to-customer binding is required
before any customer surface may consume it.

## UI truth

The Negócios Admin cockpit renders the Admin projection only under
`Negócios -> Automação B2B`.

The global execution status remains BLOQUEADA.

No button is rendered for renewal, expansion, remediation, billing, customer
contact or pilot activation.
