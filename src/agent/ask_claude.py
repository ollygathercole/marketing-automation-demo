import json
import sys

import anthropic
from dotenv import load_dotenv

from src.agent.tools import TOOL_SCHEMAS, run_tool

load_dotenv()

MODEL = "claude-sonnet-5-5"

SYSTEM = """You are a commercial analyst for Veridian Optics, a fictional ophthalmology
medical device company. You answer questions about customers, installed devices,
consumables ordering and marketing performance using ONLY the tools provided.

Rules:
- Never invent numbers. Every figure you quote must come from a tool result.
- Say clearly when something is an inference rather than something the data shows.
- Money is in pounds sterling. Use UK English.
- Refer to accounts by name and ID.
- Be concise: lead with the answer, then the evidence, then suggested next steps.
- Mention the data_as_of date when it matters to your answer.
- Use months_without_orders=6 unless the user asks for a different threshold. Never change the threshold just to make a result smaller.
- If a tool says its result is too large, retry with a smaller limit, not a different threshold.
- Where an account has a lead_change_date, compare its monthly order value before and after the change.
"""


def ask(question, max_steps=8):
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print("[tool call]", block.name, json.dumps(block.input))
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run_tool(block.name, block.input),
                })
        messages.append({"role": "user", "content": results})
    return "Stopped: Claude used too many tool calls for one question."


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m src.agent.ask_claude "your question"')
    print()
    print(ask(" ".join(sys.argv[1:])))