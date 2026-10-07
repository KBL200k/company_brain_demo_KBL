"""Smoke test: start mcp_server.py over stdio, list its tools and call a few of them.

  python scripts/test_mcp_client.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=str(ROOT),
                                   env={"PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            print("tools:", [t.name for t in listed.tools])
            calls = [
                ("list_providers", {}),
                ("lookup_products", {"product_line": "Plum"}),
                ("check_claims", {"text": "Waterproof SPF, clinically proven", "product_ids": ["P481989"]}),
                ("route_question", {"question": "Có được gọi kem chống nắng là chống nước không?"}),
                ("ask", {"question": "Thời tiết Hà Nội ngày mai thế nào?"}),
                ("ask", {"question": "Glow Lip Pop giá bao nhiêu?"}),
            ]
            for name, args in calls:
                res = await session.call_tool(name, args)
                data = res.structured_content or json.loads(res.content[0].text)
                data = data.get("result", data)
                summary = {k: data[k] for k in ("configured", "count_listings", "count_distinct_products", "ok",
                                                "blocking", "route", "mode", "answer") if k in data}
                print(f"\n{name}({args}) ->", json.dumps(summary, ensure_ascii=False, default=str)[:400])


if __name__ == "__main__":
    asyncio.run(main())
