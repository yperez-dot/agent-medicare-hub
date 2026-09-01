# Alba/BSI FMV-Cap Engine Reference

Compiled: 2026-08-13  
Status: reviewed technical reference; **observe-only until the unresolved items are closed**.

## Purpose

THEI is taking responsibility for Alba Hernandez's BSI commission statements. Any replacement split engine must be conservative: it may persist evidence and review states, but must not create or change financial allocations where the carrier source does not identify the payment type unambiguously.

## Evidence rules

Every claim in this document is one of:

- **Confirmed contract rule** — stated in a carrier document.
- **Confirmed CSV arithmetic** — mechanically verified from uploaded Humana BSI statements.
- **Review signal** — useful for routing, never sufficient to select a financial formula.
- **Unresolved** — requires a source-backed answer before automatic posting.

Do not promote a review signal or unresolved item to a financial rule without new primary-source evidence.

## Confirmed contract rules

### Humana 2026 MA/MAPD and PDP schedule

Source: `Humana_2026_Field_Commission_Schedule_100125_AGT_c1d7.pdf`.

2026 writing-agent MA rates:

| Region | Initial | Renewal |
| --- | ---: | ---: |
| National | $694 | $347 |
| CT, DC, PA | $781 | $391 |
| CA, NJ | $864 | $432 |

Puerto Rico is not listed in the supplied schedule. Do not default a PR row to National.

For a first payment following enrollment, Humana pays the Renewal Rate prorated for the months remaining in the plan year. The schedule's example is an April 1 effective date receiving `9/12` of the Renewal Rate. For a June 1 effective date:

```text
monthsRemainingInPlanYear = 13 - effectiveMonth = 7
```

For an Initial Sale, the first and second payments together equal the full Initial Commission. A row marked `First Year` does **not** by itself establish which payment stage it is.

MA/MAPD renewal payments are PMPM (`1/12` of the Renewal Rate). PDP renewals are paid annually.

Rapid disenrollment may require recovery of the entire advance. Long-term disenrollment is prorated for months not enrolled. Chargebacks must not be freshly calculated by the normal positive-payment formula.

### Aetna Agent 4 reference

The supplied Aetna Agent 4 schedule confirms the same National, CT/PA/DC, and CA/NJ dollar table above for that tier; it also places the cited Florida products at National rates.

This is **not** proof that Alba's personal compensation uses the Agent 4 tier, nor proof that UHC or Devoted uses the same table. Confirm each carrier and Alba's actual contract/upline tier before applying rates outside the documented Humana rules.

## Confirmed CSV arithmetic

In the uploaded Humana BSI statement, 39 of 40 rows satisfy:

```text
Commission ($) = Commission % × Applied To Value ($)
```

The remaining row differs by one cent due to rounding.

The labels are misleading: `Commission %` functions as a per-line rate and `Applied To Value ($)` as a per-line multiplier/unit in these records. Do not treat the latter as a dollar base for a percent calculation.

### Pablo example

The May statement contains two lines for policy `00026545711K_HMO`, each with a June 1, 2026 effective date and a January 1, 2026 original effective date:

- `32.58 × 7 = approximately 228.08`
- `13.75 × 12 = 165.00`

The first amount matches `$391 / 12 × 7 = $228.08`, supporting the documented Humana first-payment mechanism for a PA June effective date.

The two different multipliers on one policy mean `Applied To Value ($)` is not a policy-level “active months elapsed” field. Persist it only as a neutral carrier-provided unit/audit value.

## Safe review signals

### Date fields

Humana files contain both `Effective Date` and `Original EffectiveDate`.

- If the dates differ on a first-year-tagged row, return `PLAN_CHANGE_CANDIDATE`.
- If the dates differ on a renewal-tagged row, return `RENEWAL_DATE_MISMATCH`.

Both are review states. A date mismatch does not prove Like versus Unlike Plan Type Change, and genuine multi-year renewal date behavior has not yet been verified.

### Product family

Use both `Product` and `ProductType`. The real data includes labels such as:

- `Medicare Advantage HMO`
- `Medicare Advantage PPO`
- `Medicare Advantage with Prescription Drug`
- `PDP`
- `Prescription Drug`

Recognize `Medicare Advantage with Prescription Drug` as MA/MAPD before generic PDP matching. Do not treat every non-PDP product as MA/MAPD.

### Carrier-provided multiplier

Persist these values without interpreting their unit:

```text
carrier_applied_units
carrier_applied_units_raw
```

Do not name the field `carrier_applied_months` or use it to drive FMV proration.

## Required review outcomes

The engine must produce review outcomes rather than financial values where evidence is missing:

- `NEEDS_STATE`
- `NEEDS_PR_RATE`
- `NEEDS_CMS_PAYMENT_TYPE`
- `RENEWAL_DATE_MISMATCH`
- `NEEDS_ORIGIN_MATCH`
- `NEEDS_REVIEW`

Negative/chargeback rows must be held for origin matching and contract-specific proration review. “Mirror the positive row” is a proposed implementation strategy, not a confirmed carrier rule.

## Engine architecture requirements

1. Put shared split logic in one tested module. Main upload, BSI upload, and recalculation must adapt their inputs to that module instead of duplicating branches.
2. Infer source before evaluating Alba eligibility.
3. Preserve current non-Alba behavior unless a separately approved change modifies it.
4. Use integer cents for financial calculations.
5. Run Alba logic before the generic `isAgentDirectRow && hasMatchingOverride` pass-through branch only when the row has a source-backed, eligible Alba payment type.
6. Add schema changes through a migration, never route-time `ALTER TABLE`.
7. Persist the calculation version and evidence metadata with any automatically calculated Alba row:
   - bucket/review state
   - carrier and region
   - rate/cap used
   - payment stage
   - calculation version

## Product-family reference implementation

```js
function canonicalizeProductFamily(product, productType) {
  const combined = `${product || ''} ${productType || ''}`.toUpperCase();
  const isMapd =
    /\bMAPD\b|MEDICARE ADVANTAGE\s+WITH\s+PRESCRIPTION\s+DRUG/.test(combined);
  const isMa =
    /MEDICARE ADVANTAGE|\bHMO\b|\bPPO\b/.test(combined);
  const isPdp = /\bPDP\b|PRESCRIPTION DRUG/.test(combined);

  if (isMapd) return 'MA_MAPD';
  if (isMa && !isPdp) return 'MA_MAPD';
  if (isPdp && !isMa) return 'PDP';
  return 'UNKNOWN';
}
```

## Before enabling automatic financial posting

1. Verify Alba's actual carrier/upline tier.
2. Obtain Humana/YPC's source field or report that identifies CMS transaction type and payment stage.
3. Pull a real multi-year renewal with no plan change to establish date-field behavior.
4. Match several chargebacks to their originating positive payments and verify the carrier recovery calculation.
5. Obtain primary contract schedules for UHC and Devoted before reusing Aetna/Humana rules.
6. Reconcile historical correction row IDs against the database before documenting them as examples.
7. Run the engine in observe-only mode, compare a hand-checked sample, and obtain explicit approval before any batch update.

## Manual correction protocol

- Dry-run `SELECT` before each write.
- Back up the target row(s) before update.
- Use a transaction for the update and verification.
- Set `edited_by = 'system:db-console'`, `edited_at = NOW()`, and an explanatory `edit_notes` value.
- Retain the backup until the correction is independently reviewed.
