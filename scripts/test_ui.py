"""Headless test of the Streamlit UI (streamlit.testing.AppTest): chat with a follow-up question, saved
conversations (list / new / reopen / delete), and sidebar settings. Conversations it creates are deleted.

  python scripts/test_ui.py
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import history as store  # noqa: E402


def button(at, prefix):
    return next(b for b in at.sidebar.button if b.label.startswith(prefix))


def assistant_messages(at):
    return [m for m in at.chat_message if m.name == "assistant"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    before = {c["id"] for c in store.list_conversations(limit=1000)}
    at = AppTest.from_file(str(ROOT / "ui.py"), default_timeout=300)
    try:
        at.run()
        assert not at.exception, at.exception
        print("render ok | providers:", at.sidebar.selectbox[0].options)

        # answer-mode controls: defaults from .env, and the note for models without temperature
        strict = at.sidebar.multiselect(key="strict_routes")
        temp = at.sidebar.slider(key="temperature")
        print("strict routes:", strict.value, "| temperature:", temp.value)
        assert set(strict.value) == {"sop_policy", "compliance", "product_catalog"} and temp.value == 0.5
        print("no-temperature note shown for claude-opus-5:",
              any("không cho chỉnh temperature" in c.value for c in at.sidebar.caption))

        # faster runs for the test: no rerank
        at.sidebar.toggle(key="rerank").set_value(False)
        at.run()

        # 1) question + follow-up in one conversation
        at.chat_input[0].set_value("Kem dưỡng Plum Plump giá bao nhiêu?").run()
        assert not at.exception, at.exception
        at.chat_input[0].set_value("còn bản mini thì sao?").run()
        assert not at.exception, at.exception
        follow = assistant_messages(at)[-1]
        print("follow-up caption:", " | ".join(c.value for c in follow.caption))
        print("follow-up answer :", follow.markdown[0].value.splitlines()[2][:130])

        # 2) the conversation is saved and listed
        cid = at.session_state["conversation_id"]
        saved = store.get_messages(cid)
        print(f"saved conversation {cid}: {len(saved)} messages; listed in sidebar:",
              any(b.key == f"conv_{cid}" for b in at.sidebar.button))
        assert len(saved) == 4 and saved[-1]["result"]["route"]["product_ids"] == ["P479327"]
        # the stored settings only say where the key came from, never the key itself
        assert saved[-1]["result"]["settings"]["api_key"] in ("set in UI", "from environment")

        # 3) new conversation starts empty; reopening the old one restores it
        button(at, "➕").click().run()
        print("after 'new':", len(at.chat_message), "messages")
        next(b for b in at.sidebar.button if b.key == f"conv_{cid}").click().run()
        print("after reopening:", len(at.chat_message), "messages,",
              len(assistant_messages(at)[-1].caption), "detail captions on the last answer")

        # 4) delete it
        button(at, "🗑").click().run()
        print("after delete: exists =", store.conversation_exists(cid), "| messages on screen:", len(at.chat_message))
    finally:
        for c in store.list_conversations(limit=1000):
            if c["id"] not in before:
                store.delete_conversation(c["id"])


if __name__ == "__main__":
    main()
