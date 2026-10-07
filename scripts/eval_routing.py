"""Routing eval: is each question sent to the right route, and are out-of-scope questions declined?

  python scripts/eval_routing.py                    # rule router + end-to-end scope decision (no LLM needed)
  python scripts/eval_routing.py --provider gemini  # LLM router of that provider
  python scripts/eval_routing.py --router-only      # skip the end-to-end part (fast)

Measures
  route accuracy        predicted route is one of the labelled acceptable routes
  scope decision        end to end (router + relevance gate): answered vs declined, against the label
Writes data/eval/results/routing_<router>_<timestamp>.md
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rag import answer  # noqa: E402
from app.router import route_llm, route_rules  # noqa: E402

DECLINED = {"refused_out_of_scope", "refused_low_relevance"}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", help="claude | openai | gemini (LLM router); default: rule router")
    ap.add_argument("--router-only", action="store_true")
    args = ap.parse_args()
    items = [json.loads(l) for l in (ROOT / "data/eval/routing_eval.jsonl").read_text(encoding="utf-8").splitlines() if l]
    router_name = f"llm-{args.provider}" if args.provider else "rules"

    rows = []
    for it in items:
        r = route_llm(it["q"], args.provider) if args.provider else route_rules(it["q"])
        row = {"q": it["q"], "expected": it["route"], "got": r["route"], "route_ok": r["route"] in it["route"],
               "in_scope_label": it["in_scope"]}
        if not args.router_only:
            a = answer(it["q"], provider=args.provider) if args.provider else answer(it["q"])
            row["mode"] = a["mode"]
            row["declined"] = a["mode"] in DECLINED
            row["scope_ok"] = row["declined"] != it["in_scope"]
        rows.append(row)
        print(f"{'ok ' if row['route_ok'] else 'XX '}{r['route']:17} expected {'/'.join(it['route']):30} "
              + (f"{row['mode']:22} " if 'mode' in row else "") + it["q"], flush=True)

    n = len(rows)
    acc = sum(r["route_ok"] for r in rows) / n
    md = [f"# Routing eval ({router_name}, {datetime.now():%Y-%m-%d %H:%M})", "",
          f"{n} questions ({sum(not r['in_scope_label'] for r in rows)} out of scope).", "",
          f"- **Route accuracy:** {acc:.0%} ({sum(r['route_ok'] for r in rows)}/{n})"]
    if not args.router_only:
        ins = [r for r in rows if r["in_scope_label"]]
        outs = [r for r in rows if not r["in_scope_label"]]
        md += [f"- **In-scope questions answered:** {sum(not r['declined'] for r in ins)}/{len(ins)}",
               f"- **Out-of-scope questions declined:** {sum(r['declined'] for r in outs)}/{len(outs)}",
               f"- **Scope decision accuracy:** {sum(r['scope_ok'] for r in rows) / n:.0%}"]
    md += ["", "## Wrong routes", "", "| Question | Expected | Got |", "|---|---|---|"]
    md += [f"| {r['q']} | {'/'.join(r['expected'])} | {r['got']} |" for r in rows if not r["route_ok"]]
    if not args.router_only:
        md += ["", "## Wrong scope decisions", "", "| Question | In scope? | Mode |", "|---|---|---|"]
        md += [f"| {r['q']} | {r['in_scope_label']} | {r['mode']} |" for r in rows if not r["scope_ok"]]
    out = ROOT / "data/eval/results" / f"routing_{router_name}_{datetime.now():%Y%m%d-%H%M}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n" + "\n".join(md[:9]))
    print(f"\nreport: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
