"""Derive customer-insight docs from real reviews (deterministic, no LLM).

Every number is computed from data/kb/reviews.jsonl and every quote carries its review_id,
so each claim in these docs can be traced back to the raw evidence.

Output (data/kb/research/):
  insights-<product_id>.md     per product
  insights-line-<line>.md      per product line (Watermelon, Plum, ...)
  insights-overview.md         brand level
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "kb"
OUT = KB / "research"

MIN_SEGMENT = 50      # below this a segment is reported as "insufficient sample"
MIN_THEME = 20        # below this a theme is reported as "low signal"

# Brand/product names contain theme words ("Watermelon Glow", "Plum Plump", "Pore-Tight");
# strip them so naming the product is not counted as an opinion.
NAME_PHRASES = r"glow recipe|watermelon glow|glow lip pop|plum plump|pore[- ]tight|pore[- ]smooth|strawberry smooth|"                r"smoothing enzyme|dew drops|bright[- ]eye|glowy skin prep|blur drops|moisture barrier|skin barrier"
QUOTES_PER_SIDE = 2

THEMES = {
    "scent": r"\b(smell\w*|scent\w*|fragran\w*|perfume\w*)\b",
    "texture_sticky": r"\b(sticky|tacky|greasy|oily residue|film)\b",
    "texture_light": r"\b(lightweight|light weight|absorbs? (quickly|fast)|non[- ]greasy)\b",
    "hydration": r"\b(hydrat\w*|moisturized|moisturizing|plump\w*)\b",
    "glow_radiance": r"\b(glow\w*|dewy|radian\w*|brighter|brighten\w*)\b",
    "pores_texture": r"\b(pores?|smooth\w*|texture)\b",
    "irritation": r"\b(burn(ed|ing|s)?|stings?|stinging|rash\w*|itch(y|ing)|red bumps|irritated (my|me)|(caused|causes|gave me) (\w+ )?irritation)\b",
    "redness": r"\bredness\b",
    "breakouts": r"\b(break ?outs?|broke (me )?out|breaking out|pimples?|clogged|cystic|purg\w*)\b",
    "packaging": r"\b(bottle|pump|packag\w*|dropper|cap|leak\w*|jar|spray(er)?)\b",
    "price_value": r"\b(price\w*|expensive|pricey|worth|value|overpriced)\b",
    "makeup_layering": r"\b(under makeup|pill\w*|primer|layer\w*)\b",
    "white_cast": r"\b(white cast|cast)\b",
}
THEME_LABEL = {
    "scent": "Scent / fragrance",
    "texture_sticky": "Sticky or greasy feel",
    "texture_light": "Lightweight, absorbs fast",
    "hydration": "Hydration / plumping",
    "glow_radiance": "Glow / radiance",
    "pores_texture": "Pores & skin texture",
    "irritation": "Irritation (burning, stinging, rash)",
    "redness": "Redness (often 'reduces redness')",
    "breakouts": "Breakouts / clogged pores",
    "packaging": "Packaging",
    "price_value": "Price / value",
    "makeup_layering": "Makeup layering / pilling",
    "white_cast": "White cast",
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_catalog():
    """Every product doc (including minis and products without reviews), keyed by product_id."""
    catalog = {}
    for f in (KB / "products").glob("*.md"):
        text = f.read_text(encoding="utf-8")
        get = lambda k: (m.group(1).strip() if (m := re.search(rf"^{k}: (.+)$", text, re.M)) else None)
        catalog[get("product_id")] = {"name": get("title"), "line": get("product_line"),
                                      "full_size": get("full_size_product_id")}
    return catalog


def load():
    reviews = pd.read_json(KB / "reviews.jsonl", lines=True)
    text = (reviews.review_title.fillna("") + " " + reviews.review_text).str.lower()
    text = text.str.replace(NAME_PHRASES, " ", regex=True)
    for key, pattern in THEMES.items():
        reviews[key] = text.str.contains(re.sub(r"\((?!\?)", "(?:", pattern), regex=True)
    reviews["sentiment"] = pd.cut(reviews.rating, [0, 2, 3, 5], labels=["negative", "neutral", "positive"])
    reviews["year"] = pd.to_datetime(reviews.submission_time).dt.year

    lines = {}
    for f in (KB / "products").glob("*.md"):
        m = re.search(r"product_id: (\S+)\n.*?product_line: ([^\n]+)", f.read_text(encoding="utf-8"), re.S)
        lines[m.group(1)] = m.group(2).strip()
    reviews["product_line"] = reviews.product_id.map(lines)
    return reviews


def pct(x):
    return f"{x:.0%}"


def quote(row, limit=220):
    text = re.sub(r"\s+", " ", row.review_text)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."
    return f'> "{text}" - {row.rating}★, {row.skin_type or "skin type n/a"} [{row.review_id}]'


def pick_quotes(df, theme, sentiment):
    pool = df[(df[theme]) & (df.sentiment == sentiment)].copy()
    if pool.empty:
        return []
    pool["len"] = pool.review_text.str.len()
    pool = pool[(pool.len > 60)]
    pool = pool.sort_values(["helpfulness", "len"], ascending=[False, True], na_position="last")
    return [quote(r) for r in pool.head(QUOTES_PER_SIDE).itertuples()]


def summary_block(df):
    n = len(df)
    dist = df.rating.value_counts().sort_index()
    return [
        f"- **Reviews analysed:** {n}",
        f"- **Average rating:** {df.rating.mean():.2f} / 5",
        f"- **Would recommend:** {pct(df.is_recommended.mean())}",
        f"- **Mentions receiving the product free (incentivized):** {int(df.incentivized.sum())} "
        f"({pct(df.incentivized.mean())}), avg rating {df[df.incentivized].rating.mean():.2f} vs "
        f"{df[~df.incentivized].rating.mean():.2f} for the rest" if df.incentivized.any()
        else "- **Mentions receiving the product free (incentivized):** 0",
        "- **Rating distribution:** " + ", ".join(f"{k}★ {dist.get(k, 0)}" for k in range(1, 6)),
        f"- **Date range:** {df.submission_time.min():%Y-%m-%d} to {df.submission_time.max():%Y-%m-%d}",
    ]


def theme_table(df):
    pos, neg = df[df.sentiment == "positive"], df[df.sentiment == "negative"]
    rows = []
    for key in THEMES:
        n = int(df[key].sum())
        if n == 0:
            continue
        p = pos[key].mean() if len(pos) else 0
        q = neg[key].mean() if len(neg) else 0
        if n < MIN_THEME:
            lean = "low signal"
        else:
            lean = "praise" if p > q * 1.3 else "complaint" if q > p * 1.3 else "mixed"
        rows.append((key, n, n / len(df), p, q, lean))
    rows.sort(key=lambda r: -r[1])
    out = ["| Theme | Mentions | % of reviews | % of 4-5★ | % of 1-2★ | Leans |",
           "|---|---|---|---|---|---|"]
    out += [f"| {THEME_LABEL[k]} | {n} | {pct(s)} | {pct(p)} | {pct(q)} | {lean} |" for k, n, s, p, q, lean in rows]
    return out, rows


def segment_table(df, col, label):
    out = [f"| {label} | Reviews | Avg rating | Recommend | Note |", "|---|---|---|---|---|"]
    missing = df[col].isna().sum()
    for seg, g in df.groupby(col):
        note = "insufficient sample" if len(g) < MIN_SEGMENT else ""
        out.append(f"| {seg} | {len(g)} | {g.rating.mean():.2f} | {pct(g.is_recommended.mean())} | {note} |")
    out.append(f"| (not provided) | {missing} | - | - | excluded from segment stats |")
    return out


def year_table(df):
    out = ["| Year | Reviews | Avg rating |", "|---|---|---|"]
    for y, g in df.groupby("year"):
        note = " (partial year)" if y == df.year.max() else ""
        out.append(f"| {y}{note} | {len(g)} | {g.rating.mean():.2f} |")
    return out


def evidence_section(df, rows):
    out = ["## Evidence by theme", ""]
    top_praise = [r for r in rows if r[5] == "praise"][:3]
    top_complaint = ([r for r in rows if r[5] == "complaint"] + [r for r in rows if r[5] == "mixed"])[:3]
    for title, chosen, side in (("What customers praise", top_praise, "positive"),
                                ("What customers complain about", top_complaint, "negative")):
        out += [f"### {title}", ""]
        if not chosen:
            out += ["Not enough signal in the reviews to identify a theme.", ""]
        for key, n, *_ in chosen:
            quotes = pick_quotes(df, key, side)
            out.append(f"**{THEME_LABEL[key]}** ({n} mentions)")
            out.append("")
            out += quotes or ["_No representative quote found._"]
            out.append("")
    return out


def frontmatter(doc_id, title, related, scope):
    return [
        "---",
        f"doc_id: {doc_id}",
        "doc_type: customer_research",
        "source_type: derived",
        f"title: {title}",
        f"scope: {scope}",
        f"related: [{', '.join(related)}]",
        "method: keyword theme tagging + descriptive stats over reviews.jsonl (scripts/build_insights.py)",
        "data_as_of: 2023-03",
        "---",
        "",
    ]


METHOD_NOTE = [
    "## How to read this",
    "",
    "- Irritation counts only first-person reactions (burned, stung, rash, itchy); \"redness\" is tracked "
    "separately because customers mostly use it as a benefit (\"reduces redness\").",
    "- Themes are detected with keyword rules, so a mention is not always an opinion "
    "(e.g. \"no smell\" counts as a scent mention). Treat percentages as directional.",
    "- Ratings skew positive across Sephora; compare a theme's share in 1-2★ vs 4-5★ reviews "
    "rather than reading raw counts.",
    f"- Segments with fewer than {MIN_SEGMENT} reviews are flagged and should not be used for conclusions.",
    "- `incentivized` is detected from wording (\"complimentary\", \"received this for free\", ...); the source has no "
    "official flag, so some free-product reviews are missed. Do not quote incentivized reviews in ads without "
    "disclosure (brand/claims-policy CP-07).",
    "",
]


def write_doc(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_product(pid, df):
    name = df.product_name.iloc[0]
    line = df.product_line.iloc[0]
    table, rows = theme_table(df)
    doc = frontmatter(f"research/insights-{pid}", f"Customer insights: {name}",
                      [f"product/{pid}", f"research/insights-line-{slug(line)}", "research/insights-overview"],
                      f"product {pid}")
    doc += [f"# Customer insights: {name}", "", *summary_block(df), "",
            "## Themes", "", *table, "",
            *evidence_section(df, rows),
            "## By skin type", "", *segment_table(df, "skin_type", "Skin type"), "",
            "## By year", "", *year_table(df), "",
            *METHOD_NOTE]
    write_doc(OUT / f"insights-{pid}.md", doc)


def build_line(line, df, catalog):
    table, rows = theme_table(df)
    prods = df.groupby(["product_id", "product_name"]).agg(n=("rating", "size"), avg=("rating", "mean"),
                                                          rec=("is_recommended", "mean")).reset_index()
    related = ([f"research/insights-{p}" for p in prods.product_id]
               + ["research/insights-overview", "catalog/overview"])
    doc = frontmatter(f"research/insights-line-{slug(line)}", f"Customer insights: {line} line", related,
                      f"product line {line}")
    doc += [f"# Customer insights: {line} line", "", *summary_block(df), "",
            "## Products in this line", "",
            "| Product | Reviews | Avg rating | Recommend | Detail |", "|---|---|---|---|---|"]
    doc += [f"| {r.product_name} | {r.n} | {r.avg:.2f} | {pct(r.rec)} | research/insights-{r.product_id} |"
            for r in prods.sort_values("n", ascending=False).itertuples()]
    # list every product in the line, not only those with reviews, so the table is a complete inventory
    reviewed = set(prods.product_id)
    for pid, p in sorted(catalog.items(), key=lambda kv: kv[1]["name"]):
        if p["line"] != line or pid in reviewed:
            continue
        note = (f"mini size; reviews are counted under {p['full_size']}" if p["full_size"]
                else "no reviews in the knowledge base")
        doc.append(f"| {p['name']} | - | - | - | product/{pid} ({note}) |")
    n_all = sum(1 for p in catalog.values() if p["line"] == line)
    n_distinct = sum(1 for p in catalog.values() if p["line"] == line and not p["full_size"])
    doc += ["", f"{n_distinct} distinct products, {n_all} listings including minis (catalog/overview)."]
    doc += ["", "## Themes", "", *table, "", *evidence_section(df, rows),
            "## By skin type", "", *segment_table(df, "skin_type", "Skin type"), "", *METHOD_NOTE]
    write_doc(OUT / f"insights-line-{slug(line)}.md", doc)


def build_overview(df):
    table, _ = theme_table(df)
    lines = df.groupby("product_line").agg(n=("rating", "size"), avg=("rating", "mean"),
                                           rec=("is_recommended", "mean")).reset_index()
    prods = df.groupby(["product_id", "product_name"]).agg(n=("rating", "size"), avg=("rating", "mean"),
                                                          irritation=("irritation", "mean"),
                                                          breakouts=("breakouts", "mean")).reset_index()
    related = [f"research/insights-line-{slug(l)}" for l in lines.product_line]
    doc = frontmatter("research/insights-overview", "Customer insights: Glow Recipe brand overview", related, "brand")
    doc += ["# Customer insights: Glow Recipe brand overview", "", *summary_block(df), "",
            "## By product line", "",
            "| Line | Reviews | Avg rating | Recommend | Detail |", "|---|---|---|---|---|"]
    doc += [f"| {r.product_line} | {r.n} | {r.avg:.2f} | {pct(r.rec)} | research/insights-line-{slug(r.product_line)} |"
            for r in lines.sort_values("n", ascending=False).itertuples()]
    doc += ["", "## Products ranked by rating", "",
            "| Product | Reviews | Avg rating | Irritation mentions | Breakout mentions |", "|---|---|---|---|---|"]
    doc += [f"| {r.product_name} ({r.product_id}) | {r.n} | {r.avg:.2f} | {pct(r.irritation)} | {pct(r.breakouts)} |"
            for r in prods.sort_values("avg", ascending=False).itertuples()]
    doc += ["", "## Brand-wide themes", "", *table, "",
            "## By skin type", "", *segment_table(df, "skin_type", "Skin type"), "",
            "## By year", "", *year_table(df), "",
            "## Known gaps", "",
            "- No reviews in the data for: Watermelon Glow AHA Pink Dream Body Cream (P469211).",
            "- Reviews end in March 2023; nothing is known about customer sentiment after that date.",
            "- No demographic data beyond self-reported skin type / skin tone (no age, gender, location).",
            "- No purchase or repeat-purchase data; \"would recommend\" is the only loyalty signal.",
            "", *METHOD_NOTE]
    write_doc(OUT / "insights-overview.md", doc)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("insights-*.md"):
        old.unlink()
    df = load()
    for pid, g in df.groupby("product_id"):
        build_product(pid, g)
    catalog = load_catalog()
    for line, g in df.groupby("product_line"):
        build_line(line, g, catalog)
    build_overview(df)
    print(f"Wrote {len(list(OUT.glob('*.md')))} insight docs to {OUT}")


if __name__ == "__main__":
    main()
