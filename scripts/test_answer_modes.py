"""Test strict vs flexible answer modes with a fake LLM (no API key needed).

Checks: the temperature passed per route, the mode instruction in the prompt, and that strict mode rejects
answers with made-up or missing citations (falling back to the sources verbatim) while flexible mode doesn't.

  python scripts/test_answer_modes.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.rag as rag  # noqa: E402
from app.settings import Settings  # noqa: E402


class FakeLLM:
    name, model = "fake", "fake-model"

    def __init__(self, reply, supports_temperature=True):
        self.reply, self.supports_temperature, self.calls = reply, supports_temperature, []

    def chat_with_tools(self, system, user, tools, run_tool, effort="medium", temperature=None):
        self.calls.append({"temperature": temperature, "user": user})
        first_id = re.search(r'<source id="([^"]+)"', user).group(1)
        return {"text": self.reply.format(first_id=first_id), "tool_calls": [], "stop_reason": "end_turn"}


def run(question, reply, settings=None, supports_temperature=True):
    fake = FakeLLM(reply, supports_temperature)
    rag.get_llm = lambda *a, **k: fake
    res = rag.answer(question, settings=settings or Settings(rerank=False))
    call = fake.calls[0] if fake.calls else {}
    mode_line = next((l for l in call.get("user", "").splitlines() if l.startswith("Answer mode")), "")
    return res, call.get("temperature"), mode_line


def check(label, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {label}")
    return cond


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ok = True
    policy_q = "Khách có bao nhiêu ngày để trả hàng?"       # sop_policy -> strict by default
    creative_q = "Quảng cáo nào hiệu quả nhất cho Dew Drops?"  # creative  -> flexible by default

    res, temp, line = run(policy_q, "Khách có 15 ngày để trả hàng [{first_id}].")
    ok &= check(f"strict route: temperature {temp}, prompt says STRICT, cited answer kept (mode {res['mode']})",
                temp == 0.0 and "STRICT" in line and res["mode"] == "llm:fake")

    res, _, _ = run(policy_q, "Khách có 30 ngày để trả hàng [policy/made-up-rule].")
    ok &= check(f"strict route: made-up citation -> sources shown instead (mode {res['mode']})",
                res["mode"] == "strict_fallback" and "made-up" in res["llm_note"])

    res, _, _ = run(policy_q, "Thường thì khách có khoảng 30 ngày để đổi trả.")
    ok &= check(f"strict route: no citation -> sources shown instead (mode {res['mode']})",
                res["mode"] == "strict_fallback" and "no citations" in res["llm_note"])

    res, _, _ = run(policy_q, "Kho kiến thức không có đủ thông tin về việc này.")
    ok &= check(f"strict route: 'not enough information' without citation is accepted (mode {res['mode']})",
                res["mode"] == "llm:fake")

    res, temp, line = run(creative_q, "Mẫu UGC về độ glow thắng rõ, CPA giảm khoảng một phần tư.")
    ok &= check(f"flexible route: temperature {temp}, prompt says FLEXIBLE, uncited wording allowed (mode {res['mode']})",
                temp == 0.5 and "FLEXIBLE" in line and res["mode"] == "llm:fake")

    s = Settings(rerank=False, strict_routes=["sop_policy", "compliance", "product_catalog", "creative"],
                 temperature=0.8)
    res, temp, line = run(creative_q, "Mẫu UGC thắng.", settings=s)
    ok &= check(f"settings: creative made strict -> temperature {temp}, STRICT, uncited answer rejected",
                temp == 0.0 and "STRICT" in line and res["mode"] == "strict_fallback")
    res, temp, _ = run("Giọng văn thương hiệu là gì?", "Vui tươi [{first_id}].", settings=s)
    ok &= check(f"settings: flexible temperature from settings = {temp}", temp == 0.8)

    res, _, _ = run(policy_q, "Khách có 15 ngày [{first_id}].", supports_temperature=False)
    ok &= check(f"model without temperature support is reported: temperature_applied="
                f"{res['answer_mode']['temperature_applied']}", res["answer_mode"]["temperature_applied"] is False)

    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
