"""Build data/kb/catalog/catalog-overview.md: the whole product catalog in one place.

Counting and listing questions ("how many Watermelon products?", "which sizes does X come in?")
need aggregates that no single product doc contains. This doc states them explicitly, one section
per product line, so a single retrieved chunk carries the answer. Generated from the product docs
and reviews (source_type: derived), so it stays in sync with prepare_data.py.

  python scripts/build_catalog.py
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "kb"
OUT = KB / "catalog" / "catalog-overview.md"

LINE_ORDER = ["Watermelon", "Plum", "Avocado", "Strawberry", "Guava", "Blueberry", "Papaya"]
ACTIVE_LABEL = {"aha": "AHA", "bha": "BHA", "retinoid": "retinol", "sunscreen_filter": "SPF filters"}


def frontmatter(text):
    meta = {}
    for line in re.match(r"---\n(.*?)\n---\n", text, re.S).group(1).splitlines():
        k, _, v = line.partition(":")
        v = v.strip()
        meta[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()] if v.startswith("[") else v
    return meta


def field(body, name):
    m = re.search(rf"\*\*{name}:\*\* (.+)", body)
    return m.group(1).strip() if m else None


def load_products():
    products = {}
    for f in sorted((KB / "products").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        meta = frontmatter(text)
        products[meta["product_id"]] = {
            "id": meta["product_id"], "name": meta["title"], "line": meta["product_line"],
            "price": float(meta["price_usd"]), "actives": meta.get("actives") or [],
            "otc_drug": meta.get("otc_drug") == "true", "full_size": meta.get("full_size_product_id"),
            "category": field(text, "Category"), "size": field(text, "Size"), "flags": field(text, "Flags") or "",
        }
    return products


def product_type(category):
    parts = [p.strip() for p in (category or "").split(">")]
    return parts[-1] if parts and parts[-1] not in ("", "Mini Size", "Skincare") else None


def size_label(p):
    size = p["size"] if p["size"] and p["size"] != "not listed" else "size not listed"
    return f"{size} ${p['price']:.0f} ({p['id']})"


def main():
    products = load_products()
    stats = defaultdict(lambda: [0, 0.0])
    with open(KB / "reviews.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            stats[r["product_id"]][0] += 1
            stats[r["product_id"]][1] += r["rating"]

    # distinct products = full-size listings; minis attach to their full-size product
    distinct = {pid: p for pid, p in products.items() if not p["full_size"]}
    minis = defaultdict(list)
    for p in products.values():
        if p["full_size"]:
            minis[p["full_size"]].append(p)
    for p in distinct.values():
        p["minis"] = sorted(minis[p["id"]], key=lambda m: m["price"])
        p["type"] = product_type(p["category"]) or "Skincare"
        n, total = stats[p["id"]]
        p["reviews"] = f"{n} reviews, avg {total / n:.2f}★" if n else "no reviews in the knowledge base"

    by_line = defaultdict(list)
    for p in distinct.values():
        by_line[p["line"]].append(p)
    for items in by_line.values():
        items.sort(key=lambda p: p["name"])
    lines = [l for l in LINE_ORDER if l in by_line] + sorted(set(by_line) - set(LINE_ORDER))

    n_list, n_dist = len(products), len(distinct)
    n_minis = n_list - n_dist
    with_mini = [p for p in distinct.values() if p["minis"]]
    prices = [p["price"] for p in products.values()]

    md = [
        "---",
        "doc_id: catalog/overview",
        "doc_type: catalog",
        "source_type: derived",
        "title: Product catalog overview",
        "related: [brand/brand-overview, research/insights-overview, policy/shipping, brand/claims-policy]",
        "method: generated from products/*.md and reviews.jsonl by scripts/build_catalog.py",
        "data_as_of: 2023-03",
        "---",
        "",
        "# Product catalog overview",
        "",
        "## Catalog summary",
        "",
        f"The knowledge base covers **{n_list} product listings**: **{n_dist} distinct products**, "
        f"{len(with_mini)} of which are also sold as a mini, which adds {n_minis} mini listings. "
        f"They span **{len(lines)} fruit product lines**. Prices range from ${min(prices):.0f} to ${max(prices):.0f}.",
        "",
        "Glow Recipe's lip balm (Glow Lip Pop) and multi-product kits are **not** in the knowledge base.",
        "",
        "| Product line | Distinct products | Listings incl. minis | Minis | Price range | Reviews |",
        "|---|---|---|---|---|---|",
    ]
    for line in lines:
        items = by_line[line]
        listings = [p for p in products.values() if p["line"] == line]
        lp = [p["price"] for p in listings]
        nrev = sum(stats[p["id"]][0] for p in items)
        md.append(f"| {line} | {len(items)} | {len(listings)} | {len(listings) - len(items)} | "
                  f"${min(lp):.0f}–${max(lp):.0f} | {nrev:,} |")
    md.append(f"| **Total** | **{n_dist}** | **{n_list}** | **{n_minis}** | ${min(prices):.0f}–${max(prices):.0f} | "
              f"{sum(s[0] for s in stats.values()):,} |")

    for line in lines:
        items = by_line[line]
        n_l = sum(1 + len(p["minis"]) for p in items)
        n_m = n_l - len(items)
        mini_note = f", {n_l} listings including {n_m} mini{'s' if n_m != 1 else ''}" if n_m else ""
        md += ["", f"## {line} line", "",
               f"The {line} line has **{len(items)} distinct product{'s' if len(items) != 1 else ''}**{mini_note}.", "",
               "| Product | Type | Sizes and prices (product ID) | Key actives | Reviews |", "|---|---|---|---|---|"]
        for p in items:
            sizes = "; ".join([size_label(p)] + [f"mini {size_label(m)}" for m in p["minis"]])
            actives = ", ".join(ACTIVE_LABEL[a] for a in p["actives"] if a in ACTIVE_LABEL) or "-"
            md.append(f"| {p['name']} | {p['type']} | {sizes} | {actives} | {p['reviews']} |")

    md += ["", "## Products sold in more than one size", "",
           f"{len(with_mini)} products come in a full size and a mini. All other products have one size.", "",
           "| Product | Full size | Mini |", "|---|---|---|"]
    for p in sorted(with_mini, key=lambda p: p["name"]):
        md.append(f"| {p['name']} | {size_label(p)} | " + "; ".join(size_label(m) for m in p["minis"]) + " |")

    types = Counter(p["type"] for p in distinct.values())
    md += ["", "## Products by type", "",
           "Types are Sephora's category labels, kept as published (e.g. Sephora files the retinol eye cream "
           "under \"Eye Masks\").", "", "| Type | Count | Products |", "|---|---|---|"]
    for t, n in types.most_common():
        names = ", ".join(p["name"] for p in sorted(distinct.values(), key=lambda p: p["name"]) if p["type"] == t)
        md.append(f"| {t} | {n} | {names} |")

    bands = [("under $30", 0, 30), ("$30 to $39", 30, 40), ("$40 and over", 40, 1e9)]
    md += ["", "## Products by price", "",
           "Every listing, including minis. Free U.S. shipping starts at $40 (policy/shipping).", "",
           "| Price band | Count | Listings |", "|---|---|---|"]
    for label, lo, hi in bands:
        sel = sorted((p for p in products.values() if lo <= p["price"] < hi), key=lambda p: p["price"])
        md.append(f"| {label} | {len(sel)} | " + "; ".join(f"{p['name']} ${p['price']:.0f}" for p in sel) + " |")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {n_list} listings, {n_dist} distinct products, {len(lines)} lines")


if __name__ == "__main__":
    main()
