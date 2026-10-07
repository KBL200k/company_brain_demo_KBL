"""Command-line client for the Company Brain assistant.

  python cli.py "Có được gọi kem chống nắng là chống nước không?"
  python cli.py --provider gemini "Write a caption for Dew Drops"
  python cli.py                      # interactive, remembers the conversation; 'new' resets, 'exit' quits
  python cli.py --json "..."         # full result with route, sources, trace
"""
import argparse
import json
import sys

from app.history import recent_turns
from app.llm import DEFAULT_PROVIDER, PROVIDERS, available_providers
from app.rag import answer


def show(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return
    r = result["route"]
    print(f"\n[route: {r.get('route')} via {r.get('router')} | mode: {result['mode']} | "
          f"confidence: {result.get('confidence')} | {sum(result['timings_ms'].values()) / 1000:.1f}s]")
    if r.get("router_note"):
        print(f"[{r['router_note']}]")
    print("\n" + result["answer"])
    if result.get("citations") and not result["citations"]["ok"]:
        print(f"\n[!] citations not found in sources: {result['citations']['invalid']}")
    if result.get("claims_check") and result["claims_check"]["violations"]:
        print(f"\n[!] claims check: {result['claims_check']['violations']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--provider", choices=PROVIDERS, default=None, help=f"default: {DEFAULT_PROVIDER}")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-rerank", action="store_true", help="faster, slightly less accurate")
    args = ap.parse_args()
    print(f"LLM providers configured: {available_providers() or 'none (no-LLM mode)'}; default {DEFAULT_PROVIDER}",
          file=sys.stderr)

    if args.question:
        show(answer(" ".join(args.question), provider=args.provider, rerank=not args.no_rerank), args.json)
        return
    messages = []  # interactive mode remembers the session so follow-up questions work
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("exit", "quit"):
            break
        if q.lower() in ("new", "/new"):
            messages = []
            print("(new conversation)")
            continue
        if q:
            result = answer(q, provider=args.provider, rerank=not args.no_rerank, history=recent_turns(messages))
            show(result, args.json)
            messages += [{"role": "user", "content": q},
                         {"role": "assistant", "content": result["answer"], "result": result}]


if __name__ == "__main__":
    main()
