---
doc_id: research/insights-line-strawberry
doc_type: customer_research
source_type: derived
title: Customer insights: Strawberry line
scope: product line Strawberry
related: [research/insights-P482535, research/insights-P504125, research/insights-overview, catalog/overview]
method: keyword theme tagging + descriptive stats over reviews.jsonl (scripts/build_insights.py)
data_as_of: 2023-03
---

# Customer insights: Strawberry line

- **Reviews analysed:** 1579
- **Average rating:** 4.58 / 5
- **Would recommend:** 92%
- **Mentions receiving the product free (incentivized):** 192 (12%), avg rating 4.69 vs 4.57 for the rest
- **Rating distribution:** 1★ 44, 2★ 39, 3★ 59, 4★ 247, 5★ 1190
- **Date range:** 2022-03-29 to 2023-03-21

## Products in this line

| Product | Reviews | Avg rating | Recommend | Detail |
|---|---|---|---|---|
| Strawberry Smooth BHA + AHA Salicylic Acid Serum | 1027 | 4.54 | 91% | research/insights-P482535 |
| Strawberry BHA Pore-Smooth Blur Drops | 552 | 4.66 | 96% | research/insights-P504125 |

2 distinct products, 2 listings including minis (catalog/overview).

## Themes

| Theme | Mentions | % of reviews | % of 4-5★ | % of 1-2★ | Leans |
|---|---|---|---|---|---|
| Pores & skin texture | 954 | 60% | 63% | 29% | praise |
| Scent / fragrance | 658 | 42% | 42% | 36% | mixed |
| Makeup layering / pilling | 392 | 25% | 25% | 12% | praise |
| Hydration / plumping | 323 | 20% | 21% | 4% | praise |
| Packaging | 304 | 19% | 19% | 14% | praise |
| Breakouts / clogged pores | 275 | 17% | 16% | 41% | complaint |
| Glow / radiance | 261 | 17% | 18% | 2% | praise |
| Lightweight, absorbs fast | 151 | 10% | 10% | 2% | praise |
| Sticky or greasy feel | 141 | 9% | 9% | 8% | mixed |
| Price / value | 85 | 5% | 5% | 10% | complaint |
| Irritation (burning, stinging, rash) | 42 | 3% | 3% | 4% | complaint |
| Redness (often 'reduces redness') | 27 | 2% | 2% | 0% | praise |

## Evidence by theme

### What customers praise

**Pores & skin texture** (954 mentions)

> "Really liked the feel of this, skin looked great and blurred my pores." - 4★, dry [review/P504125-26202]
> "I used this for the first time and over night most of my texture was gone!" - 5★, normal [review/P482535-23081]

**Makeup layering / pilling** (392 mentions)

> "Love this primer! Definitely can see a difference in pore size after applying. Excited to see the long term benefits!" - 5★, dry [review/P504125-26077]
> "I love the consistency and really like that it has rice as an ingredient. Primer or serum alone, love the complexity of this!" - 4★, combination [review/P504125-25909]

**Hydration / plumping** (323 mentions)

> "cleared my skin up after 1week, hydrating and applied nicely to skin." - 5★, combination [review/P482535-23216]
> "I used this product as a serum and it worked really well to smoothen out my skin (blur my pores) it also felt hydrating." - 5★, oily [review/P504125-26084]

### What customers complain about

**Breakouts / clogged pores** (275 mentions)

> "used for 2 weeks, all it did was make me break out and clog all my pores. formula did not feel lightweight at all." - 1★, normal [review/P482535-23267]
> "i thought this was going to be good for my breakouts but after using it for awhile I noticed it broke me out even more" - 2★, combination [review/P482535-23335]

**Price / value** (85 mentions)

> "I’ve use this for two months now and every time I use it I don’t notice any difference. Bottle is cute, smells nice and doesn’t feel sticky on the face but for $40 it’s not worth it." - 2★, oily [review/P482535-23170]
> "I was super excited for this. I literally hit purchase as soon as I got the text message. I’m definitely disappointed. It doesn’t seem to blur much, if at all. And weirdly, there’s zero scent to mine. None at all. I..." - 2★, combination [review/P504125-25964]

**Irritation (burning, stinging, rash)** (42 mentions)

> "This has a really nice texture to it, but I won’t say it’s my favorite product. I felt like it sits really heavy on my skin and caused some irritation with consistent use. I’m not sure if it’s because of the scent (even..." - 2★, combination [review/P504125-25831]
> "For being a exfoliating product I understand this might entail some burning or irritation however it only irritates and does no good for the skin in my opinion!" - 2★, dry [review/P482535-23184]

## By skin type

| Skin type | Reviews | Avg rating | Recommend | Note |
|---|---|---|---|---|
| combination | 843 | 4.63 | 94% |  |
| dry | 256 | 4.64 | 93% |  |
| normal | 165 | 4.38 | 89% |  |
| oily | 276 | 4.53 | 90% |  |
| (not provided) | 39 | - | - | excluded from segment stats |

## How to read this

- Irritation counts only first-person reactions (burned, stung, rash, itchy); "redness" is tracked separately because customers mostly use it as a benefit ("reduces redness").
- Themes are detected with keyword rules, so a mention is not always an opinion (e.g. "no smell" counts as a scent mention). Treat percentages as directional.
- Ratings skew positive across Sephora; compare a theme's share in 1-2★ vs 4-5★ reviews rather than reading raw counts.
- Segments with fewer than 50 reviews are flagged and should not be used for conclusions.
- `incentivized` is detected from wording ("complimentary", "received this for free", ...); the source has no official flag, so some free-product reviews are missed. Do not quote incentivized reviews in ads without disclosure (brand/claims-policy CP-07).

