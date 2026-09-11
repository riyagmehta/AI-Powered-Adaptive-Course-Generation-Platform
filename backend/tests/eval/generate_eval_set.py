"""Generates ~25 (question -> expected verbatim excerpt) pairs from the eval
corpus, plus 5 hand-authored out-of-scope questions. The excerpt is checked
to be an exact substring of its module's content, so retrieval hits can be
scored by "does the expected text appear in a retrieved chunk" — a check
that stays valid no matter how the content is chunked. That's deliberate:
this eval set is re-run against different chunking schemes later, and a
scheme keyed by chunk *index* would silently break across them.

Usage:
    python -m tests.eval.generate_eval_set
"""

import asyncio
import json
from pathlib import Path

from app.config import settings
from app.services.ai_client import get_openai_client

CORPUS_PATH = Path(__file__).parent / "corpus.json"
OUTPUT_PATH = Path(__file__).parent / "eval_set.json"

QUESTIONS_PER_MODULE = 5
TARGET_PER_MODULE = 4
MAX_ATTEMPTS = 3

QUESTION_SYSTEM_PROMPT = """You write retrieval-evaluation questions for a RAG system.

Given a lesson's content, produce questions that a learner might genuinely ask about
it, each answerable from ONE specific, localized passage in the text (not the
document as a whole).

Respond with ONLY a JSON object of this shape:
{
  "items": [
    {"question": "<specific question>", "excerpt": "<10-30 word span copied VERBATIM from the text that answers it>"}
  ]
}

Rules:
- "excerpt" MUST be copied character-for-character from the provided text — no
  paraphrasing, no fixing typos, no changing punctuation or markdown.
- Each excerpt should come from a different part of the text, so the questions probe
  distinct passages rather than all clustering around the introduction.
- Prefer excerpts that contain a specific fact, term, or definition (not a vague
  sentence) so the question has one clearly correct source passage."""


OUT_OF_SCOPE_QUESTIONS = [
    "What's the best way to caramelize onions without burning them?",
    "Who won the FIFA World Cup in 1998?",
    "What are the main symptoms of seasonal allergies?",
    "How do I convert a PDF file into an editable Word document?",
    "What's a good beginner workout routine for building upper body strength?",
]


async def generate_for_module(module: dict) -> list[dict]:
    content = module["content"]
    response = await get_openai_client().chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        temperature=0.5,
        messages=[
            {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Produce {QUESTIONS_PER_MODULE} items for this lesson:\n\n{content}",
            },
        ],
    )
    payload = json.loads(response.choices[0].message.content)
    items = []
    for item in payload.get("items", []):
        excerpt = item.get("excerpt", "")
        question = item.get("question", "")
        if not question or not excerpt:
            continue
        if excerpt not in content:
            print(f"    [skip] excerpt not verbatim in module {module['index']}: {excerpt!r}")
            continue
        items.append({"question": question, "module_index": module["index"], "expected_excerpt": excerpt})
    return items


async def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text())
    modules = corpus["modules"]

    in_scope: list[dict] = []
    for module in modules:
        print(f"Generating questions for module {module['index']} ({module['title']!r})...")
        collected: list[dict] = []
        seen_excerpts: set[str] = set()
        for attempt in range(MAX_ATTEMPTS):
            if len(collected) >= TARGET_PER_MODULE:
                break
            items = await generate_for_module(module)
            for item in items:
                if item["expected_excerpt"] not in seen_excerpts:
                    seen_excerpts.add(item["expected_excerpt"])
                    collected.append(item)
            if attempt > 0:
                print(f"    retry {attempt}: now have {len(collected)} verified items")
        print(f"    got {len(collected)} verified items")
        in_scope.extend(collected)

    eval_set = {
        "corpus_topic": corpus["topic"],
        "in_scope": in_scope,
        "out_of_scope": [{"question": q} for q in OUT_OF_SCOPE_QUESTIONS],
    }
    OUTPUT_PATH.write_text(json.dumps(eval_set, indent=2))
    print(f"\nWrote {OUTPUT_PATH}: {len(in_scope)} in-scope + {len(OUT_OF_SCOPE_QUESTIONS)} out-of-scope questions")


if __name__ == "__main__":
    asyncio.run(main())
