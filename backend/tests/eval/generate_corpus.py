"""Generates the eval corpus: a real (GPT-4-authored) course with several
modules, via the actual outline/content services — not through the HTTP API
or the DB, since the eval only needs the generated text, not a persisted
course. Run once; the output is committed as a fixture.

Usage:
    python -m tests.eval.generate_corpus
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.services.content_service import generate_module_content
from app.services.outline_service import synthesize_outline

OUTPUT_PATH = Path(__file__).parent / "corpus.json"

TOPIC = "Distributed Systems Fundamentals"
NUM_MODULES = 6

FAKE_USER = SimpleNamespace(
    experience_level="intermediate",
    preferred_pace="moderate",
    topics_of_interest=["distributed systems", "backend engineering"],
    learning_goal="Understand how distributed systems handle consistency, replication, and failure.",
)


async def main() -> None:
    print(f"Synthesizing outline for {TOPIC!r} ({NUM_MODULES} modules)...")
    outline = await synthesize_outline(FAKE_USER, TOPIC, NUM_MODULES)
    course = SimpleNamespace(title=outline["title"], current_difficulty="intermediate")

    modules = []
    for i, m in enumerate(outline["modules"]):
        module = SimpleNamespace(title=m["title"], summary=m.get("summary"))
        print(f"  [{i + 1}/{len(outline['modules'])}] generating content for {m['title']!r}...")
        content = await generate_module_content(course, module)
        modules.append(
            {
                "index": i,
                "title": m["title"],
                "summary": m.get("summary"),
                "content": content,
            }
        )
        print(f"      {len(content)} chars")

    corpus = {
        "topic": TOPIC,
        "course_title": outline["title"],
        "course_description": outline.get("description"),
        "modules": modules,
    }
    OUTPUT_PATH.write_text(json.dumps(corpus, indent=2))
    print(f"\nWrote {OUTPUT_PATH} ({len(modules)} modules)")


if __name__ == "__main__":
    asyncio.run(main())
