"""RAG evaluation harness.

Indexes the eval corpus (tests/eval/corpus.json) into a dedicated Pinecone
namespace per module using the real chunking/embedding/retrieval code paths,
then runs the eval set (tests/eval/eval_set.json) against it and reports:

  - recall@1, recall@3, recall@5, MRR       (retrieval ranking quality)
  - mean retrieval latency                   (embed query + Pinecone query)
  - groundedness rate                        (LLM-as-judge, in-scope questions)
  - refusal rate                             (LLM-as-judge, out-of-scope questions)

Retrieval metrics always fetch top_k=5 (sliced for @1/@3/@5) so they're
comparable across configs. `--answer-top-k` is the production knob being
tuned — how many of those top-5 chunks actually get fed into the answer
prompt — since that's what changes between the baseline and experiment runs.

Usage:
    python -m tests.eval.run_eval --name baseline --chunk-size 1500 --chunk-overlap 200 --answer-top-k 5
    python -m tests.eval.run_eval --name experiment --chunk-size 500 --chunk-overlap 100 --answer-top-k 3
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

from app.config import settings
from app.services.ai_client import get_openai_client
from app.services.embedding_service import chunk_text, embed_text, embed_texts
from app.services.pinecone_client import query_module_context, replace_module_vectors

EVAL_DIR = Path(__file__).parent
CORPUS_PATH = EVAL_DIR / "corpus.json"
EVAL_SET_PATH = EVAL_DIR / "eval_set.json"
RESULTS_DIR = EVAL_DIR / "results"

RETRIEVAL_TOP_K = 5  # fixed, so recall@1/3/5 are comparable across configs
EVAL_COURSE_ID = -1
NAMESPACE_BASES = {"baseline": -90000, "experiment": -91000}

GROUNDING_JUDGE_PROMPT = """You are a strict fact-checking judge for a RAG system.

You'll be given the context chunks retrieved for a question, and an assistant's
answer to that question. Judge whether the answer is FULLY grounded in the given
context: every factual claim in the answer must be directly supported by the
context. If the answer includes anything not present in (or directly implied by)
the context — even something true in general, or a reasonable-sounding guess — mark
it NOT grounded. Be strict; do not give credit for plausible-sounding claims that
aren't actually backed by the provided context.

Respond with ONLY a JSON object: {"grounded": true or false, "reason": "<one sentence>"}"""

REFUSAL_JUDGE_PROMPT = """You are judging whether an assistant appropriately declined to
answer a question that the provided context does NOT cover (the context is about an
unrelated topic).

A good response acknowledges that the retrieved material doesn't address the
question, rather than fabricating an answer from outside knowledge. Mark it as
refused only if it clearly declines / says the material doesn't cover this — a
response that goes ahead and answers using general knowledge, even if the answer
itself is accurate, does NOT count as refused.

Respond with ONLY a JSON object: {"refused": true or false, "reason": "<one sentence>"}"""


def eval_module_id(config_name: str, module_index: int) -> int:
    return NAMESPACE_BASES[config_name] + module_index


async def index_corpus(config_name: str, modules: list[dict], chunk_size: int, chunk_overlap: int) -> dict:
    chunk_counts = {}
    for module in modules:
        chunks = chunk_text(module["content"], max_chars=chunk_size, overlap=chunk_overlap)
        embeddings = await embed_texts(chunks)
        await replace_module_vectors(
            eval_module_id(config_name, module["index"]), EVAL_COURSE_ID, chunks, embeddings
        )
        chunk_counts[module["index"]] = len(chunks)
    return chunk_counts


async def retrieve(config_name: str, module_index: int, question: str) -> tuple[list[dict], float]:
    start = time.perf_counter()
    embedding = await embed_text(question)
    matches = await query_module_context(eval_module_id(config_name, module_index), embedding, RETRIEVAL_TOP_K)
    latency = time.perf_counter() - start
    return matches, latency


def score_retrieval(matches: list[dict], expected_excerpt: str) -> dict:
    rank = None
    for i, match in enumerate(matches):
        if expected_excerpt in match["text"]:
            rank = i + 1
            break
    return {
        "rank": rank,
        "recall@1": rank is not None and rank <= 1,
        "recall@3": rank is not None and rank <= 3,
        "recall@5": rank is not None and rank <= 5,
        "reciprocal_rank": (1 / rank) if rank else 0.0,
    }


async def generate_answer(module_title: str, question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context was retrieved."
    system_prompt = (
        f"You are a helpful teaching assistant answering a learner's question about the module "
        f"'{module_title}'. Use the following retrieved excerpts from the module content as your "
        "primary source of truth. If the excerpts don't contain the answer, say so honestly instead "
        f"of making things up.\n\nRetrieved context:\n{context}"
    )
    response = await get_openai_client().chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.3,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
    )
    return response.choices[0].message.content


async def judge(system_prompt: str, payload: str) -> dict:
    response = await get_openai_client().chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": payload}],
    )
    return json.loads(response.choices[0].message.content)


async def run_in_scope(config_name: str, modules_by_index: dict, items: list[dict], answer_top_k: int) -> list[dict]:
    results = []
    for item in items:
        module = modules_by_index[item["module_index"]]
        matches, latency = await retrieve(config_name, item["module_index"], item["question"])
        retrieval = score_retrieval(matches, item["expected_excerpt"])

        context_chunks = [m["text"] for m in matches[:answer_top_k]]
        answer = await generate_answer(module["title"], item["question"], context_chunks)
        verdict = await judge(
            GROUNDING_JUDGE_PROMPT,
            f"Context chunks:\n{chr(10).join(context_chunks)}\n\nQuestion: {item['question']}\n\nAnswer: {answer}",
        )

        results.append(
            {
                "question": item["question"],
                "module_index": item["module_index"],
                "latency_s": latency,
                **retrieval,
                "answer": answer,
                "grounded": bool(verdict.get("grounded")),
                "grounded_reason": verdict.get("reason"),
            }
        )
        print(
            f"  [{'OK' if retrieval['rank'] else 'MISS'}] rank={retrieval['rank']} "
            f"grounded={verdict.get('grounded')} — {item['question'][:60]}"
        )
    return results


async def run_out_of_scope(config_name: str, modules: list[dict], items: list[dict], answer_top_k: int) -> list[dict]:
    # Out-of-scope questions have no "correct" module — query every module's
    # namespace and take whichever chunks score highest overall, mirroring
    # what would happen if a learner asked this on any given module page.
    results = []
    for item in items:
        best_matches: list[dict] = []
        for module in modules:
            matches, _ = await retrieve(config_name, module["index"], item["question"])
            best_matches.extend(matches)
        best_matches.sort(key=lambda m: m["score"], reverse=True)
        top_matches = best_matches[:answer_top_k]

        module_title = modules[0]["title"]  # any module's framing works here
        context_chunks = [m["text"] for m in top_matches]
        answer = await generate_answer(module_title, item["question"], context_chunks)
        verdict = await judge(
            REFUSAL_JUDGE_PROMPT,
            f"Context chunks (from an unrelated course):\n{chr(10).join(context_chunks)}\n\n"
            f"Question: {item['question']}\n\nAnswer: {answer}",
        )
        results.append(
            {
                "question": item["question"],
                "answer": answer,
                "refused": bool(verdict.get("refused")),
                "refused_reason": verdict.get("reason"),
            }
        )
        print(f"  [{'REFUSED' if verdict.get('refused') else 'ANSWERED'}] — {item['question'][:60]}")
    return results


def summarize(in_scope_results: list[dict], out_of_scope_results: list[dict], chunk_counts: dict) -> dict:
    n = len(in_scope_results)
    return {
        "num_in_scope_questions": n,
        "num_out_of_scope_questions": len(out_of_scope_results),
        "chunks_per_module": chunk_counts,
        "mean_chunks_per_module": sum(chunk_counts.values()) / len(chunk_counts),
        "recall@1": sum(r["recall@1"] for r in in_scope_results) / n,
        "recall@3": sum(r["recall@3"] for r in in_scope_results) / n,
        "recall@5": sum(r["recall@5"] for r in in_scope_results) / n,
        "mrr": sum(r["reciprocal_rank"] for r in in_scope_results) / n,
        "mean_retrieval_latency_s": sum(r["latency_s"] for r in in_scope_results) / n,
        "groundedness_rate": sum(r["grounded"] for r in in_scope_results) / n,
        "refusal_rate": sum(r["refused"] for r in out_of_scope_results) / len(out_of_scope_results),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, choices=list(NAMESPACE_BASES))
    parser.add_argument("--chunk-size", type=int, default=1500)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--answer-top-k", type=int, default=5)
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text())
    eval_set = json.loads(EVAL_SET_PATH.read_text())
    modules = corpus["modules"]
    modules_by_index = {m["index"]: m for m in modules}

    print(f"[{args.name}] indexing {len(modules)} modules (chunk_size={args.chunk_size}, overlap={args.chunk_overlap})...")
    chunk_counts = await index_corpus(args.name, modules, args.chunk_size, args.chunk_overlap)
    print(f"  chunk counts: {chunk_counts}")

    print(f"\n[{args.name}] running {len(eval_set['in_scope'])} in-scope questions (answer_top_k={args.answer_top_k})...")
    in_scope_results = await run_in_scope(args.name, modules_by_index, eval_set["in_scope"], args.answer_top_k)

    print(f"\n[{args.name}] running {len(eval_set['out_of_scope'])} out-of-scope questions...")
    out_of_scope_results = await run_out_of_scope(args.name, modules, eval_set["out_of_scope"], args.answer_top_k)

    summary = summarize(in_scope_results, out_of_scope_results, chunk_counts)
    report = {
        "config": {
            "name": args.name,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "retrieval_top_k": RETRIEVAL_TOP_K,
            "answer_top_k": args.answer_top_k,
        },
        "summary": summary,
        "in_scope_results": in_scope_results,
        "out_of_scope_results": out_of_scope_results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{args.name}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== {args.name} summary ===")
    for k, v in summary.items():
        if k == "chunks_per_module":
            continue
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
