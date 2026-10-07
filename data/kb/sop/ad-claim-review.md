---
doc_id: sop/ad-claim-review
doc_type: sop
source_type: synthetic
title: "SOP: Ad & copy claim review"
owner: Regulatory & Quality (fictional role)
version: 1.2
effective: 2023-03-01
related: [brand/claims-policy, brand/voice-guide, compliance/ftc-health-claims, compliance/fda-cosmetic-vs-drug, creative/learnings-2023]
---

> **SYNTHETIC DOCUMENT.** This was written for the demo knowledge base. It is not a real Glow Recipe internal document.

# SOP: Ad & copy claim review

## Purpose

Every piece of customer-facing copy is checked against brand/claims-policy before it goes live. This includes AI-generated drafts.

## Roles

| Role | Responsibility |
|---|---|
| Copy owner (Growth / Creative) | Writes copy, runs the self-check, submits it |
| Copy reviewer (Brand Creative) | Checks voice and GUIDE-level rules |
| Regulatory reviewer (Regulatory & Quality) | Decides REVIEW items and maintains the claims register |

## Steps

1. **Self-check (copy owner).** Run the checklist below. Tag each product mentioned with its product ID.
2. **Classify.** If any BLOCK rule is hit, rewrite before submitting. If any REVIEW rule is hit, submit to Regulatory. If only GUIDE rules apply, submit to the copy reviewer.
3. **Submit** in the #claims-review channel with: copy, product IDs, channel, launch date, and the rule IDs it touches.
4. **SLA:**
   - GUIDE review: 1 business day.
   - REVIEW (Regulatory): 3 business days.
   - Paid social launches need approval at least **5 business days** before the flight date.
5. **Record.** Regulatory logs approved REVIEW claims in the **claims register** with the claim text, product ID, evidence or study ID, approver and expiry date (12 months).
6. **Post-launch.** If a live ad is found to break a BLOCK rule, pause it within 4 hours and log an incident.

## Self-check checklist

- [ ] No disease or treatment words (CP-01).
- [ ] BHA products do not mention acne treatment and do not promise "no breakouts" (CP-02).
- [ ] Dark-spot copy uses "the look of" (CP-03).
- [ ] AHA products: Sunburn Alert or SPF mention where required (CP-04).
- [ ] Sunscreen: no sunblock/waterproof/sweatproof, reapply language included, no absolute "no white cast" (CP-05).
- [ ] No clinical, % or "dermatologist" claims without a register ID (CP-06).
- [ ] Review quotes are verbatim, have a review_id, and contain no blocked claims (CP-07).
- [ ] No "chemical-free", "non-toxic" or "fragrance-free" unless true (CP-09).
- [ ] Creator posts open with #ad (CP-10).
- [ ] Price and shipping match product docs and policy/shipping (CP-11).

## Claims register status (as of 2023-04-01)

| Claim | Product | Status |
|---|---|---|
| Water resistant (any duration) | P481989 | **Not approved.** No test result on file. |
| Broad spectrum | P481989 | **Not approved.** Test result not in the knowledge base. |
| "Clinically proven" (any product benefit) | all | **Not approved.** No study on file. |
| "Dermatologist tested" | all | **Not approved.** No evidence on file. |
| "#1" / "best-selling" | all | **Not approved.** No sales-rank evidence on file. |

## AI-generated copy

AI drafts go through the same steps. The drafting tool must:

- list the rule IDs it checked
- keep the review_id for every quote
- mark any claim it could not verify as **NEEDS REVIEW** instead of removing it silently
