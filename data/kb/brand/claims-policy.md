---
doc_id: brand/claims-policy
doc_type: brand_compliance
source_type: synthetic
title: Marketing claims policy (internal rulebook)
owner: Regulatory & Quality (fictional role)
version: 2.1
effective: 2023-04-01
related: [compliance/fda-cosmetic-vs-drug, compliance/fda-aha-labeling, compliance/fda-sunscreen-labeling, compliance/ftc-health-claims, compliance/ftc-endorsement-guides, brand/voice-guide, sop/ad-claim-review]
---

> **SYNTHETIC DOCUMENT.** This was written for the demo knowledge base. It is not a real Glow Recipe internal document. The rules apply real FDA/FTC sources (linked per rule) to real products in the catalog.

# Marketing claims policy

This policy applies to **all** customer-facing copy: ads, PDP copy, emails, SMS, social posts, influencer briefs, customer-care replies and AI-generated drafts.

**Severity levels**

- **BLOCK:** the copy must not ship. Rewrite it or escalate to Regulatory.
- **REVIEW:** the copy may ship only after Regulatory sign-off, recorded in the claims register (sop/ad-claim-review).
- **GUIDE:** a style requirement. The copy reviewer fixes it directly.

---

## CP-01 No disease or treatment claims (BLOCK)

Skincare products here are cosmetics. Copy may describe **appearance**. It must not describe treating, curing, healing or preventing a condition.
Source: compliance/fda-cosmetic-vs-drug.

| Do not write | Write instead |
|---|---|
| treats / cures / heals | helps skin look / feel ... |
| eczema, rosacea, psoriasis, dermatitis | (do not name medical conditions) |
| repairs your skin barrier | supports a healthy-looking skin barrier |
| anti-inflammatory | soothing, calming-feeling |
| regenerates cells, boosts collagen | smoother, plumper-looking skin |

## CP-02 BHA / salicylic acid products: no acne-treatment claims (BLOCK)

Applies to: P482535 Strawberry Smooth BHA + AHA Salicylic Acid Serum, P504125 Strawberry BHA Pore-Smooth Blur Drops, P458219 / P467762 Watermelon Glow PHA + BHA Pore-Tight Toner.

- Do not write: "treats acne", "clears breakouts", "acne treatment", "gets rid of pimples", "prevents breakouts".
- Allowed: "helps unclog the look of pores", "smoother-looking texture", "for skin with visible pores".
- **Do not promise "no breakouts" or "won't break you out".** In research/insights-P482535, 24% of reviews mention breakouts or purging, and so do 47% of 1-2★ reviews. Recommend a patch test and gradual introduction.

## CP-03 Dark spots and brightening (BLOCK)

Applies to: Guava line (P475543, P501760) and any vitamin C copy.

- Allowed: "reduces the look of dark spots", "brighter-looking skin", "more even-looking tone".
- Do not write: "fades melasma", "reduces melanin", "lightening", "whitening", "bleaching", "removes hyperpigmentation".

## CP-04 AHA products: sun-sensitivity disclosure (REVIEW)

Applies to products with AHAs (compliance/fda-aha-labeling): P501254 / P501570 Watermelon Glow AHA Night Treatment, P436359 / P441323 Blueberry Bounce Gentle Cleanser, P482535 Strawberry Smooth serum, P469211 Pink Dream Body Cream.

- PDP, educational and routine content must include the FDA Sunburn Alert, or a link to it.
- Routine content featuring these products must show or mention **daily SPF**.
- Do not write "safe for daytime sun exposure" or "no sun sensitivity".
- AHA % and pH are **not** in the knowledge base. Do not state them.

## CP-05 Sunscreen is an OTC drug (BLOCK)

Applies to: P481989 Watermelon Glow Niacinamide Sunscreen SPF 50. Source: compliance/fda-sunscreen-labeling.

- Never use: "sunblock", "waterproof", "sweatproof".
- "Water resistant (40/80 minutes)" and "broad spectrum": only if the claims register holds the test result. The register has no such entry, so **REVIEW**.
- Do not write "all-day protection" or "no need to reapply". Any usage copy must say "reapply at least every 2 hours".
- Do not write **"no white cast"** or "invisible on all skin tones" as absolute claims. In research/insights-P481989, 26% of reviews mention white cast, with mixed sentiment.
- Do not write "won't pill under makeup". Pilling is the top complaint for this product: 68% of 1-2★ reviews mention it.

## CP-06 Clinical, test and expert claims (REVIEW)

- "Clinically proven", "clinically tested", "dermatologist tested/recommended", "% of users saw ...", "results in X days" all need a study ID in the claims register. Source: compliance/ftc-health-claims.
- The public tagline "Clinically Effective" may be used **only** as the brand tagline, never attached to a specific product benefit without a study ID.
- The knowledge base contains **no clinical study data**. Any request to write such a claim must be flagged as needing Regulatory input.

## CP-07 Using customer reviews in marketing (REVIEW)

Source: compliance/ftc-endorsement-guides, compliance/ftc-health-claims.

- Quote reviews **verbatim**. Keep the review_id so it can be traced.
- A quoted review becomes **our claim**. Rules CP-01 to CP-06 apply to the quote too. For example, "this cleared my acne" is blocked.
- Do not imply that one review's result is typical. Choose quotes that reflect the theme's real share in research/insights-* docs.
- Do not suppress or hide negative reviews. Do not offer incentives conditional on positive reviews.

## CP-08 Retinol eye cream (BLOCK)

Applies to: P447791 Avocado Fine Line Eye Cream with Retinol.

- Allowed: "reduces the look of fine lines", "smoother-looking under-eye area".
- Do not write: "erases wrinkles", "reverses aging", "Botox in a jar", "anti-aging treatment".
- Usage copy must say: use at night, wear SPF during the day, patch test. Copy should advise anyone pregnant or breastfeeding to consult a doctor before using retinol products.

## CP-09 "Clean", "natural" and "safe" language (BLOCK)

- Never use: "chemical-free", "non-toxic", "toxin-free", "100% natural", "safe for everyone".
- "Clean" may be used only as "part of Clean at Sephora" or "Clean + Planet Positive at Sephora", and only for products whose highlights list that label.
- "Vegan" and "cruelty-free" are allowed. They are public brand commitments (brand/brand-overview).
- **"Fragrance-free"** may be used only when the product's ingredient list has no fragrance/parfum. Most products contain fragrance (`actives: [fragrance]` in the product docs). Do not call those products suitable "for sensitive skin" without REVIEW.

## CP-10 Influencer and creator disclosure (BLOCK)

Every paid or gifted post must open with "#ad" or "Ad", shown in the video itself and in the caption above the fold. "#gifted" alone is not enough. Source: compliance/ftc-endorsement-guides. See sop/influencer-brief.

## CP-11 Price, promotion and shipping claims (GUIDE)

- Prices must match the product doc (`price_usd`). If the price differs between sources, use the product doc and flag the conflict.
- Free-shipping copy must say "on U.S. orders $40+" (policy/shipping).
- Do not describe returns more generously than policy/returns allows (15 days, excludes sheet masks and international orders).

## CP-12 Comparative and superlative claims (REVIEW)

"Best", "#1", "better than [competitor]", "the only ..." need substantiation in the claims register. Sephora sales ranks and awards are not in the knowledge base.

---

## Quick lookup by product

| Product | ID | Rules that always apply |
|---|---|---|
| Watermelon Glow Niacinamide Sunscreen SPF 50 | P481989 | CP-05, CP-06 |
| Strawberry Smooth BHA + AHA Salicylic Acid Serum | P482535 | CP-02, CP-04 |
| Strawberry BHA Pore-Smooth Blur Drops | P504125 | CP-02 |
| Watermelon Glow PHA + BHA Pore-Tight Toner | P458219, P467762 | CP-02 |
| Watermelon Glow AHA Night Treatment | P501254, P501570 | CP-04 |
| Blueberry Bounce Gentle Cleanser | P436359, P441323 | CP-04 |
| Guava Vitamin C Dark Spot Treatment Serum | P475543 | CP-03 |
| Guava Vitamin C Bright-Eye Gel Cream | P501760 | CP-03 |
| Avocado Fine Line Eye Cream with Retinol | P447791 | CP-08 |
| Avocado Soothing Skin Barrier Serum | P470529 | CP-01 (no "repairs barrier", no "treats redness") |
| All products | - | CP-01, CP-06, CP-07, CP-09, CP-11, CP-12 |
