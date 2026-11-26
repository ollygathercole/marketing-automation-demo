import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("ANTHROPIC_API_KEY not found in .env")

client = anthropic.Anthropic()
reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=100,
    messages=[{
        "role": "user",
        "content": "In one sentence, say hello to Veridian Optics' marketing team.",
    }],
)
print(reply.content[0].text)
print("Tokens used:", reply.usage.input_tokens, "in,", reply.usage.output_tokens, "out")