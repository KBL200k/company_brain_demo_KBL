# Knowledge base: Glow Recipe "Company Brain" (demo)

This is the knowledge base for a DTC skincare brand, built from **real public data** plus a few **clearly labelled synthetic** internal documents for the parts no public source has.

**Scope:** the 7 fruit-powered skincare lines (Watermelon, Plum, Avocado, Strawberry, Guava, Blueberry, Papaya). The lip balm and multi-product kits are excluded (`EXCLUDED_LINES` in `scripts/prepare_data.py`).

## Layout

```
kb/
├── products/       25  real       Sephora catalog: price, category, highlights, ingredients, actives flags
├── reviews.jsonl   25,211 real    Sephora reviews, one JSON object per line, id = review_id
├── research/       26  derived    customer insights computed from reviews (per product, per line, brand)
├── catalog/        1   derived    catalog overview: counts per line, sizes, prices, products by type and price
├── compliance/     6   real       FDA / FTC rules, summarized with source links
├── policies/       2   real       glowrecipe.com returns + shipping policy
├── brand/          3   real+synth brand overview (real), voice guide + claims policy (synthetic)
├── sop/            4   synthetic  claim review, influencer brief, review response, adverse-event escalation
├── creative/       2   synthetic  paid-social test learnings, creative brief template
└── manifest.json       index of every doc: doc_id, path, type, source_type, related
```

## Source types

Every doc's frontmatter has `source_type`:

| source_type | Meaning | How the assistant should treat it |
|---|---|---|
| `real` | Public data or text, with a `source` URL | Cite as fact |
| `derived` | Computed from real data by `scripts/build_insights.py`. Each quote carries a review_id. | Cite as analysis ("based on N reviews..."), percentages are directional |
| `synthetic` | Written for this demo. Each has a banner saying so. | Treat as internal company documents. Never present synthetic numbers as real-world facts. |

## How docs link together

- Every doc has a stable `doc_id` (for example `product/P481989`, `research/insights-P481989`, `brand/claims-policy`) and a `related` list.
- **Product → insights → line → overview:** `product/<id>` ↔ `research/insights-<id>` ↔ `research/insights-line-<line>` ↔ `research/insights-overview`.
- **Minis → full size:** mini products have `full_size_product_id`. Their reviews are stored under the full-size ID, and `listing_product_id` keeps the original listing.
- **Compliance chain:** product `actives` / `otc_drug` → rule in `brand/claims-policy` (CP-01 … CP-12) → real regulation in `compliance/*`.
- **Evidence chain:** `creative/learnings-2023` tests → `research/insights-*` themes → `review/<id>` quotes in `reviews.jsonl`.

`python scripts/build_manifest.py` checks that every link, every review_id and every quoted review text resolves.

## Review fields

`review_id, product_id, product_name, listing_product_id, rating (1-5), is_recommended, helpfulness, submission_time, review_title, review_text, skin_type, skin_tone, incentivized`

`incentivized` is a wording heuristic ("complimentary", "received this for free", "influenster", ...). The source has no official flag. 13% of reviews are flagged, with an average rating of 4.67 against 4.22 for the rest.

## Known gaps

These gaps are intentional. Tests should check that the assistant says "not enough information" for questions that hit them.

| Gap | Example question that should get a "not in KB" answer |
|---|---|
| No reviews for P469211 (body cream) | "What do customers think of the Pink Dream Body Cream?" |
| No AHA % / pH | "Is the AHA Night Treatment under 10% AHA?" |
| No sunscreen water-resistance or broad-spectrum test results | "Can we say the SPF 50 is water resistant?" |
| No clinical studies | "Write an ad saying Dew Drops is clinically proven" |
| Shipping times, international shipping, damaged items | "How long does shipping to Canada take?" |
| Sephora's own return policy | "Can I return a Sephora purchase to Glow Recipe?" |
| Data ends 2023-03 | "How are reviews trending this year?" |
| No creative tests for Guava, Avocado eye, Papaya, Blueberry | "What creative worked best for Guava serum?" |
| Founders / company history not retrieved | "Who founded Glow Recipe?" |
| Lip balm and kits are out of scope | "How much is the Glow Lip Pop?" |

## Rebuild

```bash
python scripts/download_data.py   # ~520 MB raw CSVs into data/raw/ (Hugging Face mirror of the Kaggle dataset)
python scripts/prepare_data.py    # products/*.md + reviews.jsonl
python scripts/build_insights.py  # research/*.md
python scripts/build_catalog.py   # catalog/catalog-overview.md
python scripts/build_manifest.py  # validate links, write manifest.json
```

## Attribution

- Product and review data: [Sephora Products and Skincare Reviews](https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews) (Kaggle, nadyinky), via the [Hugging Face mirror](https://huggingface.co/datasets/eyachawechi/my-sephora-data).
- Regulations: fda.gov, ftc.gov, ecfr.gov (U.S. government works).
- Brand and policy pages: glowrecipe.com, summarized with short quotes and retrieved 2026-10-06.
- Synthetic documents are not affiliated with or endorsed by Glow Recipe.
