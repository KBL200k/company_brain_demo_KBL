---
doc_id: research/insights-line-guava
doc_type: customer_research
source_type: derived
title: Customer insights: Guava line
scope: product line Guava
related: [research/insights-P475543, research/insights-P501760, research/insights-overview, catalog/overview]
method: keyword theme tagging + descriptive stats over reviews.jsonl (scripts/build_insights.py)
data_as_of: 2023-03
---

# Customer insights: Guava line

- **Reviews analysed:** 1672
- **Average rating:** 4.39 / 5
- **Would recommend:** 85%
- **Mentions receiving the product free (incentivized):** 61 (4%), avg rating 4.80 vs 4.37 for the rest
- **Rating distribution:** 1★ 82, 2★ 93, 3★ 97, 4★ 226, 5★ 1174
- **Date range:** 2021-09-04 to 2023-03-21

## Products in this line

| Product | Reviews | Avg rating | Recommend | Detail |
|---|---|---|---|---|
| Guava Vitamin C Bright-Eye Gel Cream | 922 | 4.49 | 88% | research/insights-P501760 |
| Guava Vitamin C Dark Spot Treatment Serum | 750 | 4.26 | 81% | research/insights-P475543 |

2 distinct products, 2 listings including minis (catalog/overview).

## Themes

| Theme | Mentions | % of reviews | % of 4-5★ | % of 1-2★ | Leans |
|---|---|---|---|---|---|
| Glow / radiance | 684 | 41% | 45% | 15% | praise |
| Hydration / plumping | 588 | 35% | 39% | 11% | praise |
| Packaging | 557 | 33% | 30% | 47% | complaint |
| Pores & skin texture | 551 | 33% | 37% | 10% | praise |
| Scent / fragrance | 543 | 32% | 35% | 18% | praise |
| Lightweight, absorbs fast | 249 | 15% | 18% | 0% | praise |
| Sticky or greasy feel | 245 | 15% | 16% | 6% | praise |
| Makeup layering / pilling | 217 | 13% | 15% | 3% | praise |
| Price / value | 114 | 7% | 4% | 19% | complaint |
| Breakouts / clogged pores | 68 | 4% | 3% | 10% | complaint |
| Irritation (burning, stinging, rash) | 54 | 3% | 3% | 4% | complaint |
| Redness (often 'reduces redness') | 17 | 1% | 1% | 1% | low signal |

## Evidence by theme

### What customers praise

**Glow / radiance** (684 mentions)

> "Skin does glow more but haven’t noticed a huge decrees in dark spots." - 4★, combination [review/P475543-19503]
> "Since I’m using this, my skin feels good and it has started glowing. So far it is very good product" - 4★, dry [review/P475543-19390]

**Hydration / plumping** (588 mentions)

> "Immediately after using this eye cream the darkness significantly went away. It’s really moisturizing and I will definitely be buying another!" - 5★, dry [review/P501760-24834]
> "So creamy! This formula is a little thicker than the serum, and its a perfect pairing. I definitely noticed a difference in my skin around my eyes for sure." - 5★, combination [review/P501760-24821]

**Pores & skin texture** (551 mentions)

> "One of the best Vitamin C product! I just love the texture and feeling on my face! Works best with Plum plump as well! Big fan of the brand!" - 5★, normal [review/P475543-19434]
> "I’m really loving this eye cream! The texture and consistency is really nice and my dark circles have definitely faded in the couple weeks I’ve been using it! My eyes look bright! Very pleased!" - 5★, normal [review/P501760-24772]

### What customers complain about

**Packaging** (557 mentions)

> "Used everyday till the bottle was empty and saw no change in my dark spots." - 2★, combination [review/P475543-19525]
> "The pump was absolutely terrible. It stops dispensing cream when there is still half the product left. This cream was moisturizing but that’s about it." - 1★, oily [review/P501760-24992]

**Price / value** (114 mentions)

> "Kind of sticky and have not seen any results. Not worth trying." - 2★, combination [review/P475543-19559]
> "there were no changes. i usually love everything glow recipe but this was a bust. no changes and for the price i expected more." - 2★, dry [review/P501760-24990]

**Breakouts / clogged pores** (68 mentions)

> "I was so excited when I first got this and was expecting some of my scars to fade a but after only one use it broke me out so bad, it wasn’t even moisturizing. Disappointed" - 1★, combination [review/P475543-19572]
> "I wanted to love this product. Texture is nice and smooth. Unfortunately it made me breakout on my forehead. I don’t usually have acne but do get small breakouts on my forehead. I literally had the worst acne of my life..." - 2★, normal [review/P475543-19313]

## By skin type

| Skin type | Reviews | Avg rating | Recommend | Note |
|---|---|---|---|---|
| combination | 880 | 4.45 | 86% |  |
| dry | 345 | 4.45 | 88% |  |
| normal | 203 | 4.30 | 83% |  |
| oily | 203 | 4.24 | 80% |  |
| (not provided) | 41 | - | - | excluded from segment stats |

## How to read this

- Irritation counts only first-person reactions (burned, stung, rash, itchy); "redness" is tracked separately because customers mostly use it as a benefit ("reduces redness").
- Themes are detected with keyword rules, so a mention is not always an opinion (e.g. "no smell" counts as a scent mention). Treat percentages as directional.
- Ratings skew positive across Sephora; compare a theme's share in 1-2★ vs 4-5★ reviews rather than reading raw counts.
- Segments with fewer than 50 reviews are flagged and should not be used for conclusions.
- `incentivized` is detected from wording ("complimentary", "received this for free", ...); the source has no official flag, so some free-product reviews are missed. Do not quote incentivized reviews in ads without disclosure (brand/claims-policy CP-07).

