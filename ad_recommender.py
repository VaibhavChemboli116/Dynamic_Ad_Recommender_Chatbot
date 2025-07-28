"""
Dynamic Ad‑Recommender Chatbot (stream‑safe)

• Tracks the conversation.
• After every 4th user question it checks topical coherence with GPT‑4o‑mini.
• If coherent, it appends ONE sponsored product link obtained from SerpApi to the same reply.
• Works indefinitely: links may appear at turns 4,8,12,… provided coherence holds.
• Uses streaming completions so answers never truncate mid‑sentence.
• Thread‑safe by design—no background threads required.
• Compatible with openai‑python ≥ 1.0 and serpapi ≥ 2.0.
"""

import os
import time
import json
import warnings
from dotenv import load_dotenv
from openai import OpenAI
from serpapi import GoogleSearch
import urllib3

# ────────────────────────── optional: silence LibreSSL on macOS ──────────────────────────
warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)

# ────────────────────────── configuration ──────────────────────────
DEBUG             = True      # set False to silence [DEBUG] prints
OPENAI_MODEL      = "gpt-4o-mini"
GPT_MAX_TOKENS    = 800
MAX_BUFFER_SIZE   = 100       # max Q/A lines kept in memory (each counts as one line)

load_dotenv()                  # expects OPENAI_API_KEY and SERPAPI_KEY in .env or env

# ────────────────────────── clients ──────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY in your environment or .env file")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("Set SERPAPI_KEY in your environment or .env file")

# ────────────────────────── helper: streaming completion ──────────────────────────

def _stream_chat(messages, temperature=0.7, max_tokens=GPT_MAX_TOKENS):
    """Return the full streamed completion as a string (blocking)."""
    stream = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    parts = []
    for chunk in stream:
        if chunk.choices[0].delta.content:
            parts.append(chunk.choices[0].delta.content)
    return "".join(parts).strip()

# ────────────────────────── main orchestrator class ──────────────────────────

class AdRecommender:
    """Rule‑based orchestrator that injects product links every 4th coherent Q."""

    TRIGGER_QS = 4            # fire on each 4th user question
    SNAPSHOT_LINES = 7        # 3 Q‑A pairs (6) + current question (1)

    def __init__(self):
        self.buffer: list[str] = []   # alternating lines: "Q: …", "A: …"
        self.msg_cnt = 0              # counts user questions only

    # ────────────── GPT judge: are last 4 Q‑A pairs on the same topic? ──────────────
    def _judge_topic(self, snapshot: str):
        sys_msg = (
            "Determine whether the last 4 Q&A pairs share one topic and suggest a product or service.\n\n"
            "If yes, respond exactly:\n"
            "RELATED: yes\nTOPIC: <topic>\nP/S: <product>\n\n"
            "Else respond exactly:\n"
            "RELATED: no\nTOPIC: None\nP/S: None"
        )
        raw = _stream_chat(
            [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": snapshot + "\nRELATED:"},
            ],
            temperature=0.2,
            max_tokens=256,
        )
        if DEBUG:
            print("\n[DEBUG] judge_topic raw:\n" + raw)
        lines = raw.splitlines()
        related = lines[0].strip().lower().endswith("yes") if lines else False
        topic = lines[1].split(":", 1)[1].strip() if len(lines) > 1 else "None"
        ps = lines[2].split(":", 1)[1].strip() if len(lines) > 2 else "None"
        return related, topic, ps

    # ────────────── SerpApi shopping search ──────────────
    def _shopping_search(self, query: str):
        if DEBUG:
            print(f"[DEBUG] SerpApi search for: '{query}'")
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": "us",
            "hl": "en",
            "num": "10",
            "direct_link": "1",
            "tbs": "vw:l",
            "api_key": SERPAPI_KEY,
        }
        try:
            results = GoogleSearch(params).get_dict()
            item = (results.get("shopping_results") or [{}])[0]
            link = item.get("link") or item.get("product_link") or ""
            if not link:
                return None
            return {
                "name": item.get("title", ""),
                "link": link,
                "desc": (item.get("snippet") or item.get("description") or "")[:160] + "…",
            }
        except Exception as exc:
            if DEBUG:
                print(f"[shop‑err] {exc}")
            return None

    # ────────────── public entry point ──────────────
    def chat(self, user_msg: str) -> str:
        # 1. buffer bookkeeping
        self.buffer.append(f"Q: {user_msg}")
        self.msg_cnt += 1
        if len(self.buffer) > MAX_BUFFER_SIZE:
            self.buffer = self.buffer[-MAX_BUFFER_SIZE:]

        # 2. collect conversation context for the assistant
        ctx = []
        for i in range(0, len(self.buffer), 2):
            if i + 1 < len(self.buffer):
                ctx += [
                    {"role": "user", "content": self.buffer[i][3:]},
                    {"role": "assistant", "content": self.buffer[i + 1][3:]},
                ]
        ctx.append({"role": "user", "content": user_msg})

        answer = _stream_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Format responses using markdown: "
                        "**bold** for emphasis, *italic* for subtle emphasis, `code` for terms, and lists. "
                        "Preserve any links exactly as provided."
                    ),
                },
                *ctx,
            ]
        )

        # 3. on every 4th question decide if we should append an ad
        if self.msg_cnt == self.TRIGGER_QS:
            snapshot = "\n".join(self.buffer[-self.SNAPSHOT_LINES:])
            related, topic, ps = self._judge_topic(snapshot)
            if related and ps.lower() != "none":
                product = self._shopping_search(ps)
                if product:
                    answer += (
                        f"\n\n▶ Because you've been talking about **{topic}**, "
                        f"you might like: [{product['name']}]({product['link']}) — {product['desc']}"
                    )
            # reset counter regardless of outcome
            self.msg_cnt = 0

        # 4. store assistant answer and return
        self.buffer.append(f"A: {answer}")
        return answer

# ────────────────────────── simple CLI to demo the bot ──────────────────────────

def main():
    print("Dynamic Ad Chat – type 'quit' to exit.")
    bot = AdRecommender()
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if user_input.lower() == "quit":
            break
        print("\nAI:", bot.chat(user_input))


if __name__ == "__main__":
    main()
