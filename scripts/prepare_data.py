"""Build the product + review part of the knowledge base from the raw Sephora dataset.

Source: Kaggle "Sephora Products and Skincare Reviews" (nadyinky),
mirrored on Hugging Face at eyachawechi/my-sephora-data.

Output (data/kb/):
  products/<product_id>_<slug>.md   one markdown doc per product, with frontmatter
  reviews.jsonl                     one review per line, with a stable review_id
"""
import ast
import json
import re
from pathlib import Path

import pandas as pd

BRAND = "Glow Recipe"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
KB = ROOT / "data" / "kb"
SOURCE_URL = "https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews"

REVIEW_COLS = [
    "product_id", "product_name", "rating", "is_recommended", "helpfulness",
    "submission_time", "review_title", "review_text", "skin_type", "skin_tone",
]

# Product line = the fruit in the name; used to link products, insights and creative tests.
LINES = ["Watermelon", "Plum", "Avocado", "Papaya", "Blueberry", "Strawberry", "Guava"]
KIT_KEYWORDS = ("Kit", "Set", "Duo")
# The knowledge base focuses on the fruit lines; lip balm and multi-product kits are dropped.
EXCLUDED_LINES = {"Lip", "Kits"}

# Ingredient markers that trigger compliance rules in brand/claims-policy.
ACTIVE_MARKERS = {
    "aha": ("glycolic", "lactic acid", "mandelic"),
    "bha": ("salicylic",),
    "retinoid": ("retinol", "retinal", "retinyl"),
    "sunscreen_filter": ("zinc oxide", "avobenzone", "homosalate", "octisalate", "octocrylene"),
    "fragrance": ("fragrance", "parfum"),
}


# Reviewer says the product was free (sampling programs, PR). Heuristic; the source has no such column.
INCENTIVE_PATTERN = (r"complimentary|received (this|it|the product)( \w+)? (for )?free|got (this|it) (for )?free|"
                     r"free (sample|product|in exchange)|in exchange for (my|an) (honest )?review|gifted|influenster|"
                     r"provided (to me )?by|sent (to )?me (by|from)")


def fix_text(s):
    """The source CSV replaced curly quotes/accents with U+FFFD; most are apostrophes."""
    if not isinstance(s, str):
        return s
    return s.replace("�", "'").strip()


def parse_list(s):
    if not isinstance(s, str):
        return []
    try:
        return [fix_text(x) for x in ast.literal_eval(s)]
    except (ValueError, SyntaxError):
        return [fix_text(s)]


def product_line(name):
    if "Lip" in name:
        return "Lip"
    if name.endswith(KIT_KEYWORDS):
        return "Kits"
    return next((line for line in LINES if line in name), "Other")


def detect_actives(ingredients_raw, name):
    text = f"{ingredients_raw} {name}".lower()
    found = [k for k, words in ACTIVE_MARKERS.items() if any(w in text for w in words)]
    for acid in ("aha", "bha"):  # the name states the acid even when the INCI list uses another name
        if re.search(rf"\b{acid}\b", name.lower()) and acid not in found:
            found.append(acid)
    return found


def fmt_price(row):
    price = f"${row.price_usd:.2f}"
    if pd.notna(row.sale_price_usd):
        price += f" (on sale: ${row.sale_price_usd:.2f})"
    if pd.notna(row.value_price_usd):
        price += f" (value price: ${row.value_price_usd:.2f})"
    return price


def yaml_list(items):
    return "[" + ", ".join(items) + "]"


def product_md(row, stats, full_size_id, has_insights):
    name = fix_text(row.product_name)
    flags = [f for f in ("new", "limited_edition", "online_only", "sephora_exclusive", "out_of_stock") if row[f] == 1]
    category = " > ".join(str(c) for c in (row.primary_category, row.secondary_category, row.tertiary_category)
                          if pd.notna(c))
    highlights = parse_list(row.highlights)
    ingredients = parse_list(row.ingredients)
    actives = detect_actives(row.ingredients, name)
    is_otc_drug = "sunscreen_filter" in actives

    review_owner = full_size_id or row.product_id
    related = []
    if has_insights:
        related.append(f"research/insights-{review_owner}")
    if full_size_id:
        related.append(f"product/{full_size_id}")
    related += ["brand/claims-policy", f"research/insights-line-{slug(row.line)}"]

    fm = [
        "---",
        f"doc_id: product/{row.product_id}",
        "doc_type: product",
        "source_type: real",
        f"title: {name}",
        f"product_id: {row.product_id}",
        f"product_line: {row.line}",
        f"brand: {row.brand_name}",
        f"price_usd: {row.price_usd:.2f}",
        f"actives: {yaml_list(actives)}",
        f"otc_drug: {str(is_otc_drug).lower()}",
    ]
    if full_size_id:
        fm.append(f"full_size_product_id: {full_size_id}")
    fm += [
        f"related: {yaml_list(related)}",
        f"source: Sephora product catalog, {SOURCE_URL}",
        "data_as_of: 2023-03",
        "---",
    ]

    lines = fm + [
        "",
        f"# {name}",
        "",
        f"- **Product ID:** {row.product_id}",
        f"- **Product line:** {row.line}",
        f"- **Category:** {category or 'unknown'}",
        f"- **Price:** {fmt_price(row)}",
        f"- **Size:** {fix_text(row['size']) if pd.notna(row['size']) else 'not listed'}",
    ]
    if pd.notna(row.variation_type):
        lines.append(f"- **Variation:** {row.variation_type}: {fix_text(row.variation_value)}")
    if flags:
        lines.append(f"- **Flags:** {', '.join(flags)}")
    if is_otc_drug:
        lines.append("- **Regulatory status:** OTC drug (sunscreen) - see brand/claims-policy rule CP-05")
    lines += [
        f"- **Sephora rating (as listed on Sephora):** {row.rating:.2f} / 5 from {int(row.reviews)} reviews"
        if pd.notna(row.rating) else "- **Sephora rating:** not available",
        f"- **Loves count:** {int(row.loves_count)}",
    ]
    if full_size_id:
        lines.append(f"- **Reviews:** Sephora shares reviews between sizes; reviews for this mini are stored "
                     f"under the full-size product {full_size_id}.")
    elif stats:
        lines.append(f"- **Reviews in this knowledge base:** {stats['n']} "
                     f"(avg rating {stats['avg']:.2f}, {stats['rec']:.0%} recommend)")
    else:
        lines.append("- **Reviews in this knowledge base:** none")
    lines += ["", "## Highlights", ""]
    lines += [f"- {h}" for h in highlights] if highlights else ["- none listed"]
    lines += ["", "## Ingredients", ""]
    lines += ["\n\n".join(ingredients) if ingredients else "Not listed in the source data."]
    return "\n".join(lines) + "\n"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_reviews(ids, full_size):
    parts = []
    for f in sorted(RAW.glob("reviews_*.csv")):
        if "masked" in f.name:
            continue
        df = pd.read_csv(f, usecols=REVIEW_COLS, dtype={"product_id": str}, low_memory=False)
        parts.append(df[df.product_id.isin(ids)])
        print(f"  scanned {f.name}")
    reviews = pd.concat(parts, ignore_index=True).dropna(subset=["review_text"])
    for col in ("review_title", "review_text", "product_name"):
        reviews[col] = reviews[col].map(fix_text)
    # Sephora shows the same reviews on mini and full-size listings; keep the full-size copy.
    before = len(reviews)
    reviews["_is_mini"] = reviews.product_name.str.startswith("Mini ")
    reviews = (reviews.sort_values("_is_mini")
               .drop_duplicates(subset=["review_text", "submission_time", "rating"])
               .drop(columns="_is_mini"))
    print(f"  dropped {before - len(reviews)} duplicate reviews")
    # Attach mini-only reviews to the full-size product; keep the original listing for traceability.
    reviews["listing_product_id"] = reviews.product_id
    reviews["product_id"] = reviews.product_id.map(lambda pid: full_size.get(pid) or pid)
    names = reviews.drop_duplicates("listing_product_id").set_index("listing_product_id").product_name
    reviews["product_name"] = reviews.product_id.map(lambda pid: names.get(pid, pid))
    text = (reviews.review_title.fillna("") + " " + reviews.review_text).str.lower()
    reviews["incentivized"] = text.str.contains(re.sub(r"\((?!\?)", "(?:", INCENTIVE_PATTERN), regex=True)
    reviews = reviews.sort_values(["product_id", "submission_time"]).reset_index(drop=True)
    reviews.insert(0, "review_id", [f"review/{pid}-{i:05d}" for i, pid in enumerate(reviews.product_id)])
    return reviews


def main():
    products = pd.read_csv(RAW / "product_info.csv")
    products = products[products.brand_name == BRAND].copy()
    products["product_name"] = products.product_name.map(fix_text)
    products["line"] = products.product_name.map(product_line)
    print(f"{BRAND}: {len(products)} products")

    by_name = dict(zip(products.product_name, products.product_id))
    full_size = {
        r.product_id: by_name.get(r.product_name[len("Mini "):])
        for r in products.itertuples() if r.product_name.startswith("Mini ")
    }

    # IDs are assigned over the full brand catalog first, then non-fruit rows are dropped,
    # so review_ids stay stable whatever is excluded (cited quotes and the Qdrant index keep matching).
    reviews = load_reviews(set(products.product_id), full_size)
    dropped = products[products.line.isin(EXCLUDED_LINES)]
    products = products[~products.line.isin(EXCLUDED_LINES)]
    reviews = reviews[reviews.product_id.isin(set(products.product_id))]
    print(f"  excluded lines {sorted(EXCLUDED_LINES)}: {len(dropped)} products "
          f"({', '.join(dropped.product_id)})")
    stats = {
        pid: {"n": len(g), "avg": g.rating.mean(), "rec": g.is_recommended.mean()}
        for pid, g in reviews.groupby("product_id")
    }

    out_products = KB / "products"
    out_products.mkdir(parents=True, exist_ok=True)
    for old in out_products.glob("*.md"):
        old.unlink()
    for _, row in products.iterrows():
        fs = full_size.get(row.product_id)
        owner = fs or row.product_id
        doc = product_md(row, stats.get(row.product_id), fs, has_insights=owner in stats)
        (out_products / f"{row.product_id}_{slug(row.product_name)[:50]}.md").write_text(doc, encoding="utf-8")

    with open(KB / "reviews.jsonl", "w", encoding="utf-8") as f:
        for rec in reviews.to_dict(orient="records"):
            rec = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in rec.items()}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(products)} product docs and {len(reviews)} reviews to {KB}")
    print("mini -> full size:", full_size)


if __name__ == "__main__":
    main()
