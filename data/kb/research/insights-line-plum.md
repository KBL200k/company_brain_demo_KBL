---
doc_id: research/insights-line-plum
doc_type: customer_research
source_type: derived
title: Customer insights: Plum line
scope: product line Plum
related: [research/insights-P462699, research/insights-P479327, research/insights-overview, catalog/overview]
method: keyword theme tagging + descriptive stats over reviews.jsonl (scripts/build_insights.py)
data_as_of: 2023-03
---

# Customer insights: Plum line

- **Reviews analysed:** 3374
- **Average rating:** 4.44 / 5
- **Would recommend:** 87%
- **Mentions receiving the product free (incentivized):** 562 (17%), avg rating 4.68 vs 4.39 for the rest
- **Rating distribution:** 1★ 116, 2★ 132, 3★ 244, 4★ 538, 5★ 2344
- **Date range:** 2020-08-25 to 2023-03-21

## Products in this line

| Product | Reviews | Avg rating | Recommend | Detail |
|---|---|---|---|---|
| Plum Plump Hyaluronic Acid Serum | 1918 | 4.42 | 87% | research/insights-P462699 |
| Plum Plump Hyaluronic Acid Moisturizer | 1456 | 4.46 | 88% | research/insights-P479327 |
| Mini Plum Plump Hyaluronic Acid Moisturizer | - | - | - | product/P500472 (mini size; reviews are counted under P479327) |

2 distinct products, 3 listings including minis (catalog/overview).

## Themes

| Theme | Mentions | % of reviews | % of 4-5★ | % of 1-2★ | Leans |
|---|---|---|---|---|---|
| Hydration / plumping | 1971 | 58% | 62% | 26% | praise |
| Scent / fragrance | 1020 | 30% | 31% | 18% | praise |
| Packaging | 992 | 29% | 30% | 21% | praise |
| Glow / radiance | 963 | 29% | 32% | 8% | praise |
| Pores & skin texture | 853 | 25% | 28% | 12% | praise |
| Sticky or greasy feel | 668 | 20% | 19% | 29% | complaint |
| Lightweight, absorbs fast | 457 | 14% | 15% | 2% | praise |
| Price / value | 324 | 10% | 8% | 20% | complaint |
| Makeup layering / pilling | 281 | 8% | 8% | 9% | mixed |
| Breakouts / clogged pores | 206 | 6% | 4% | 26% | complaint |
| Irritation (burning, stinging, rash) | 42 | 1% | 1% | 4% | complaint |
| Redness (often 'reduces redness') | 25 | 1% | 1% | 1% | complaint |
| White cast | 1 | 0% | 0% | 0% | low signal |

## Evidence by theme

### What customers praise

**Hydration / plumping** (1971 mentions)

> "Love this clean product! It’s so hydrating! Definitely recommend!" - 5★, nan [review/P462699-13648]
> "Love this serum. It smells wonderful and feels super moisturizing." - 5★, oily [review/P462699-13987]

**Scent / fragrance** (1020 mentions)

> "Love this serum. It smells wonderful and feels super moisturizing." - 5★, oily [review/P462699-13987]
> "I recieved it in my TRENDMOOD box i really enjoy it.Smells so good and leaves my skin refreshing" - 5★, dry [review/P462699-12864]

**Packaging** (992 mentions)

> "Skin feels hydrated and light after applying this product. One pump is enough." - 5★, dry [review/P462699-13695]
> "Glow Recipe is my favorite skin care line. Love this new product! Adorable packaging and great hydration!" - 5★, combination [review/P462699-14114]

### What customers complain about

**Sticky or greasy feel** (668 mentions)

> "Unfortunately not a big fan. Left me feeling greasy. Nice subtle scent though" - 2★, combination [review/P479327-20719]
> "Received this from Influenster. It left a sticky film on my face, and if I’d layered additional products on top, it likely would’ve pilled. For the price point, certainly not worth the purchase." - 2★, dry [review/P462699-13121]

**Price / value** (324 mentions)

> "Didn’t like this one mainly because it made me break out. My skin WAS soft but not the worth the breakouts." - 2★, combination [review/P462699-13904]
> "I enjoyed the texture and light scent of this product, but for the price you are better off going with Inkey List HA for same results." - 2★, combination [review/P462699-14004]

**Breakouts / clogged pores** (206 mentions)

> "The absolute worst not for my dry skin girlies at all :(( so disappointed" - 1★, dry [review/P479327-20609]
> "Gave me the worst breakout I’ve ever had! I will be returning and will going back to using Osea." - 1★, combination [review/P462699-14104]

## By skin type

| Skin type | Reviews | Avg rating | Recommend | Note |
|---|---|---|---|---|
| combination | 1771 | 4.46 | 88% |  |
| dry | 766 | 4.42 | 87% |  |
| normal | 457 | 4.39 | 86% |  |
| oily | 322 | 4.49 | 90% |  |
| (not provided) | 58 | - | - | excluded from segment stats |

## How to read this

- Irritation counts only first-person reactions (burned, stung, rash, itchy); "redness" is tracked separately because customers mostly use it as a benefit ("reduces redness").
- Themes are detected with keyword rules, so a mention is not always an opinion (e.g. "no smell" counts as a scent mention). Treat percentages as directional.
- Ratings skew positive across Sephora; compare a theme's share in 1-2★ vs 4-5★ reviews rather than reading raw counts.
- Segments with fewer than 50 reviews are flagged and should not be used for conclusions.
- `incentivized` is detected from wording ("complimentary", "received this for free", ...); the source has no official flag, so some free-product reviews are missed. Do not quote incentivized reviews in ads without disclosure (brand/claims-policy CP-07).

