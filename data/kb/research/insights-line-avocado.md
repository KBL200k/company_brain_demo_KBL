---
doc_id: research/insights-line-avocado
doc_type: customer_research
source_type: derived
title: Customer insights: Avocado line
scope: product line Avocado
related: [research/insights-P447791, research/insights-P470529, research/insights-P503634, research/insights-overview, catalog/overview]
method: keyword theme tagging + descriptive stats over reviews.jsonl (scripts/build_insights.py)
data_as_of: 2023-03
---

# Customer insights: Avocado line

- **Reviews analysed:** 3931
- **Average rating:** 4.29 / 5
- **Would recommend:** 83%
- **Mentions receiving the product free (incentivized):** 881 (22%), avg rating 4.70 vs 4.17 for the rest
- **Rating distribution:** 1★ 215, 2★ 216, 3★ 303, 4★ 682, 5★ 2515
- **Date range:** 2019-08-09 to 2023-03-19

## Products in this line

| Product | Reviews | Avg rating | Recommend | Detail |
|---|---|---|---|---|
| Avocado Fine Line Eye Cream with Retinol | 1884 | 4.10 | 78% | research/insights-P447791 |
| Avocado Soothing Skin Barrier Serum with Ceramides | 1417 | 4.47 | 87% | research/insights-P470529 |
| Avocado Ceramide Moisture Barrier Cleanser | 630 | 4.43 | 89% | research/insights-P503634 |

3 distinct products, 3 listings including minis (catalog/overview).

## Themes

| Theme | Mentions | % of reviews | % of 4-5★ | % of 1-2★ | Leans |
|---|---|---|---|---|---|
| Hydration / plumping | 1367 | 35% | 37% | 18% | praise |
| Pores & skin texture | 1032 | 26% | 30% | 7% | praise |
| Scent / fragrance | 904 | 23% | 24% | 13% | praise |
| Packaging | 885 | 23% | 21% | 25% | mixed |
| Redness (often 'reduces redness') | 860 | 22% | 23% | 17% | praise |
| Glow / radiance | 582 | 15% | 17% | 4% | praise |
| Price / value | 412 | 10% | 8% | 19% | complaint |
| Sticky or greasy feel | 293 | 7% | 8% | 3% | praise |
| Lightweight, absorbs fast | 275 | 7% | 8% | 1% | praise |
| Irritation (burning, stinging, rash) | 157 | 4% | 3% | 10% | complaint |
| Breakouts / clogged pores | 139 | 4% | 3% | 7% | complaint |
| Makeup layering / pilling | 119 | 3% | 3% | 2% | praise |

## Evidence by theme

### What customers praise

**Hydration / plumping** (1367 mentions)

> "Yes yes yes! Made my skin look so much more smooth and hydrated." - 5★, combination [review/P470529-17377]
> "Nice product, hydrates my eyes. Not much effects with fine lines and wrinkles." - 4★, dry [review/P447791-06395]

**Pores & skin texture** (1032 mentions)

> "Love love love this! Goes on smooth and feels great under my eye" - 5★, combination [review/P447791-06403]
> "Yes yes yes! Made my skin look so much more smooth and hydrated." - 5★, combination [review/P470529-17377]

**Scent / fragrance** (904 mentions)

> "I have dark circles and this has helped with them a lot in only a few days, it also smells nice" - 5★, combination [review/P447791-05978]
> "It’s smooth and lathers easily and it removes makeup very well. It doesn’t have a strong scent." - 4★, oily [review/P503634-25190]

### What customers complain about

**Price / value** (412 mentions)

> "Idk broke out badly and the packaging was not good at all disappointing cause it’s so expensive" - 1★, combination [review/P503634-25652]
> "It feels nice on my face, but I’ve been using it for about 3 months and don’t see a difference. Not worth the price." - 2★, combination [review/P470529-17668]

**Irritation (burning, stinging, rash)** (157 mentions)

> "THIS IS THE !!WORST!! EYE CREAM. THIS BURNED MY EYE CONTOUR ON THE SECOND DAY AND I GET LINES THAT DID NOT HAVE. THE WORST BUY." - 1★, combination [review/P447791-06576]
> "I have very sensitive skin I thought this product will be perfectly safe for me. Unfortunately as soon i used it I had red and itching spots" - 1★, combination [review/P470529-17364]

**Breakouts / clogged pores** (139 mentions)

> "I used it for about a week and all it did was make me feel greasy and broke me out." - 2★, oily [review/P470529-17387]
> "Idk broke out badly and the packaging was not good at all disappointing cause it’s so expensive" - 1★, combination [review/P503634-25652]

## By skin type

| Skin type | Reviews | Avg rating | Recommend | Note |
|---|---|---|---|---|
| combination | 2137 | 4.31 | 84% |  |
| dry | 732 | 4.24 | 80% |  |
| normal | 454 | 4.23 | 82% |  |
| oily | 433 | 4.21 | 83% |  |
| (not provided) | 175 | - | - | excluded from segment stats |

## How to read this

- Irritation counts only first-person reactions (burned, stung, rash, itchy); "redness" is tracked separately because customers mostly use it as a benefit ("reduces redness").
- Themes are detected with keyword rules, so a mention is not always an opinion (e.g. "no smell" counts as a scent mention). Treat percentages as directional.
- Ratings skew positive across Sephora; compare a theme's share in 1-2★ vs 4-5★ reviews rather than reading raw counts.
- Segments with fewer than 50 reviews are flagged and should not be used for conclusions.
- `incentivized` is detected from wording ("complimentary", "received this for free", ...); the source has no official flag, so some free-product reviews are missed. Do not quote incentivized reviews in ads without disclosure (brand/claims-policy CP-07).

