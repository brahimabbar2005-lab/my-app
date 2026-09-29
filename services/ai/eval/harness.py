"""Run the golden-question evaluation.

    python -m eval.harness --limit 20                 quick pass
    python -m eval.harness --category Transport       one category
    python -m eval.harness --full --rubric            everything, with model grading
    python -m eval.harness --multi-turn               the 10 constraint-tracking tests
    python -m eval.harness --offline                  no model: retrieval/link/affiliate only
    python -m eval.harness --compare reports/prev.json

The `--offline` mode is the one that runs in CI. It exercises classification,
retrieval, link selection, affiliate gating and content-gap detection without
an API key, so a regression in the parts that are deterministic gets caught on
every commit rather than on a nightly model run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.core.intent import classify_rules
from app.core.llm import ModelUnavailable, complete_json
from app.core.orchestrator import get_orchestrator
from app.knowledge.affiliates import select_affiliates
from app.knowledge.links import detect_content_gap, select_links
from app.knowledge.loader import get_knowledge_base
from app.knowledge.retriever import get_retriever
from app.schemas import TripState
from eval.scorers import (
    QuestionResult,
    RUBRIC_PROMPT,
    Score,
    build_rubric_payload,
    mechanical,
    retrieval_score,
    rubric_scores,
    structural,
)

REPORTS = ROOT / "eval" / "reports"


# ---------------------------------------------------------------------------
async def run_offline(row: dict[str, Any]) -> QuestionResult:
    """No model. Checks everything deterministic about the pipeline."""
    retriever = get_retriever()
    question = row["question"]
    classification = classify_rules(question)
    candidates = retriever.retrieve(question, classification)
    links = select_links(candidates, classification)
    affiliates = select_affiliates(
        question, classification, TripState(), retriever.kb.programs, retriever.kb.activities
    )
    gap = detect_content_gap(question, candidates, classification)

    # A missing link is only a retrieval failure if the site actually has
    # something to find. When the gap detector fires, the right page does not
    # exist — that is an editorial finding, not a broken retriever, so it is
    # recorded rather than scored against the pipeline.
    retrieval = retrieval_score(row, [r.title for r in links.resources])
    if gap:
        retrieval = Score("retrieval", retrieval.value, True,
                          f"site gap — no page covers this ({retrieval.detail})")
    scores: list[Score] = [retrieval]

    affiliate_expected = (row.get("affiliate_relevant") or "No").lower() == "yes"
    shown = bool(affiliates.cards)
    if not affiliate_expected and shown:
        scores.append(Score("affiliate_discipline", 0.0, False, "affiliate on a non-commercial question"))
    else:
        scores.append(Score("affiliate_discipline", 1.0, True, affiliates.reason_blocked or "shown appropriately"))

    live_expected = (row.get("live_data_required") or "No").lower() == "yes"
    detected = classification.needs_live_data
    scores.append(
        Score("live_data_detection", 1.0 if detected == live_expected else 0.0,
              detected == live_expected,
              f"expected {live_expected}, detected {detected}")
    )

    scores.append(Score("link_discipline", 1.0 if len(links.resources) <= 4 else 0.0,
                        len(links.resources) <= 4, f"{len(links.resources)} link(s)"))

    return QuestionResult(
        question_id=row["id"],
        question=question,
        answer="",
        scores=scores,
        resources=[r.title for r in links.resources],
        affiliates=[c.name for c in affiliates.cards],
        content_gap=bool(gap),
    )


async def run_one(row: dict[str, Any], *, use_rubric: bool) -> QuestionResult:
    orchestrator = get_orchestrator()
    started = time.perf_counter()
    result = await orchestrator.answer(row["question"])
    elapsed = int((time.perf_counter() - started) * 1000)

    resources = [r.title for r in result.resources]
    affiliates = [c.name for c in result.affiliates]

    scores = mechanical(result.answer)
    scores += structural(result.answer, row, resources, affiliates)
    scores.append(retrieval_score(row, resources))

    if use_rubric:
        try:
            verdict = await complete_json(
                RUBRIC_PROMPT, build_rubric_payload(row, result.answer), max_tokens=600
            )
            scores += rubric_scores(verdict)
        except (ModelUnavailable, ValueError) as exc:
            scores.append(Score("rubric", 0.0, False, f"rubric failed: {exc}"))

    return QuestionResult(
        question_id=row["id"],
        question=row["question"],
        answer=result.answer,
        scores=scores,
        failures=[s.name for s in scores if not s.passed],
        resources=resources,
        affiliates=affiliates,
        latency_ms=elapsed,
        tokens=result.usage.total,
    )


async def run_multi_turn(test: dict[str, Any]) -> dict[str, Any]:
    """Constraint tracking across turns.

    Each test's point is that something said in turn 1 or 2 must survive — or
    must be dropped — by the final turn. The check is whether the trip state
    carries it, which is testable without judging prose.
    """
    orchestrator = get_orchestrator()
    trip = TripState()
    history: list[dict[str, str]] = []
    turns_out = []

    for turn in test["turns"]:
        result = await orchestrator.answer(turn, history=history, trip=trip)
        trip = result.trip
        history.append({"role": "user", "content": turn})
        history.append({"role": "assistant", "content": result.answer})
        turns_out.append({"user": turn, "assistant": result.answer,
                          "trip_state": trip.to_dict()})

    return {
        "id": test["id"],
        "expected_behaviour": test["expected_behaviour"],
        "tests": test["tests"],
        "turns": turns_out,
        "final_trip_state": trip.to_dict(),
    }


# ---------------------------------------------------------------------------
def summarise(results: list[QuestionResult]) -> dict[str, Any]:
    by_scorer: dict[str, list[float]] = defaultdict(list)
    passes: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        for score in result.scores:
            by_scorer[score.name].append(score.value)
            passes[score.name].append(score.passed)

    failures: dict[str, int] = defaultdict(int)
    for result in results:
        for name in result.failures:
            failures[name] += 1

    latencies = [r.latency_ms for r in results if r.latency_ms]

    return {
        "questions": len(results),
        "passed": sum(1 for r in results if r.passed),
        "pass_rate": round(sum(1 for r in results if r.passed) / len(results), 3) if results else 0,
        "overall_score": round(statistics.mean([r.overall for r in results]), 3) if results else 0,
        "by_scorer": {name: round(statistics.mean(values), 3) for name, values in sorted(by_scorer.items())},
        # A scorer can pass while scoring low — retrieval on a question the
        # site has no page for, for example. Both numbers are reported so the
        # distinction stays visible.
        "pass_rate_by_scorer": {
            name: round(sum(values) / len(values), 3) for name, values in sorted(passes.items())
        },
        "failure_counts": dict(sorted(failures.items(), key=lambda kv: -kv[1])),
        "latency_p50_ms": int(statistics.median(latencies)) if latencies else None,
        "latency_p90_ms": int(sorted(latencies)[int(len(latencies) * 0.9)]) if len(latencies) > 4 else None,
        "total_tokens": sum(r.tokens for r in results),
        "content_gaps": sum(1 for r in results if r.content_gap),
    }


def compare(current: dict[str, Any], previous_path: Path) -> None:
    previous = json.loads(previous_path.read_text())
    prev = previous["summary"]
    cur = current["summary"]

    print("\nComparison against", previous_path.name)
    print(f"  {'metric':24} {'before':>9} {'after':>9} {'delta':>9}")
    for key in ("pass_rate", "overall_score"):
        before, after = prev.get(key, 0), cur.get(key, 0)
        print(f"  {key:24} {before:>9.3f} {after:>9.3f} {after - before:>+9.3f}")
    for name in sorted(set(prev.get("by_scorer", {})) | set(cur.get("by_scorer", {}))):
        before = prev.get("by_scorer", {}).get(name, 0)
        after = cur.get("by_scorer", {}).get(name, 0)
        marker = "  <-- regression" if after < before - 0.02 else ""
        print(f"  {name:24} {before:>9.3f} {after:>9.3f} {after - before:>+9.3f}{marker}")


def print_report(summary: dict[str, Any], results: list[QuestionResult], show_failures: int) -> None:
    print("\n" + "=" * 68)
    print("GOLDEN QUESTION EVALUATION")
    print("=" * 68)
    print(f"  questions       {summary['questions']}")
    print(f"  passed          {summary['passed']}  ({summary['pass_rate'] * 100:.1f}%)")
    print(f"  overall score   {summary['overall_score']}")
    if summary.get("latency_p50_ms"):
        print(f"  latency p50/p90 {summary['latency_p50_ms']}ms / {summary['latency_p90_ms']}ms")
    if summary.get("total_tokens"):
        print(f"  tokens          {summary['total_tokens']:,}")
    print(f"  content gaps    {summary.get('content_gaps', 0)}  "
          f"(questions the site has no page for — editorial backlog, not a defect)")

    print(f"\n  by scorer{'':14}{'score':>7}{'pass':>7}")
    rates = summary.get("pass_rate_by_scorer", {})
    for name, value in summary["by_scorer"].items():
        rate = rates.get(name, 0.0)
        bar = "#" * int(value * 22)
        print(f"    {name:22} {value:6.3f} {rate:6.1%}  {bar}")

    if summary["failure_counts"]:
        print("\n  failures")
        for name, count in summary["failure_counts"].items():
            print(f"    {name:22} {count}")

    worst = sorted([r for r in results if not r.passed], key=lambda r: r.overall)[:show_failures]
    if worst:
        print("\n  worst answers")
        for result in worst:
            print(f"\n    [{result.question_id}] {result.overall}  {result.question[:88]}")
            print(f"      failed: {', '.join(result.failures)}")
            for score in result.scores:
                if not score.passed and score.detail:
                    print(f"        {score.name}: {score.detail[:150]}")
            if result.answer:
                print(f"      answer: {result.answer[:220].replace(chr(10), ' ')}...")


# ---------------------------------------------------------------------------
async def main() -> int:
    parser = argparse.ArgumentParser(description="ComeMorocco AI golden-question evaluation")
    parser.add_argument("--limit", type=int, default=25, help="how many questions (default 25)")
    parser.add_argument("--full", action="store_true", help="run the whole dataset")
    parser.add_argument("--category", help="filter by dataset category")
    parser.add_argument("--difficulty", help="filter by difficulty: Easy, Medium, Hard")
    parser.add_argument("--rubric", action="store_true", help="add model-based rubric grading")
    parser.add_argument("--offline", action="store_true", help="no model calls")
    parser.add_argument("--multi-turn", action="store_true", help="run the multi-turn tests")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--compare", type=Path, help="compare against a previous report")
    parser.add_argument("--out", type=Path, help="where to write the report")
    args = parser.parse_args()

    kb = get_knowledge_base()
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if args.multi_turn:
        tests = kb.multi_turn_tests
        print(f"Running {len(tests)} multi-turn tests...")
        outputs = []
        for test in tests:
            outputs.append(await run_multi_turn(test))
            print(f"  {test['id']} done")
        path = args.out or REPORTS / f"multi-turn-{stamp}.json"
        path.write_text(json.dumps({"tests": outputs}, ensure_ascii=False, indent=1))
        print(f"\nWritten to {path}")
        print("These need a human read: the expectation is behavioural, not a score.")
        return 0

    rows = kb.golden_questions
    if args.category:
        rows = [r for r in rows if (r.get("category") or "").lower() == args.category.lower()]
    if args.difficulty:
        rows = [r for r in rows if (r.get("difficulty") or "").lower() == args.difficulty.lower()]
    if not args.full:
        rows = rows[: args.limit]

    if not rows:
        print("No questions matched those filters.")
        return 1

    mode = "offline" if args.offline else ("model + rubric" if args.rubric else "model")

    from app.config import get_settings

    settings = get_settings()
    if not args.offline and settings.on_free_tier:
        per_question = (1 + (2 if settings.model_classification_enabled else 0)
                        + (1 if settings.quality_check_enabled else 0) + (1 if args.rubric else 0))
        needed = per_question * len(rows)
        print(f"Free model: this run needs about {needed} requests "
              f"({per_question} per question). OpenRouter allows 50 a day without purchased "
              "credits, and 20 a minute.")
        if needed > 45 and input("Continue? [y/N] ").strip().lower() != "y":
            print("Stopped. Use --limit to run fewer questions, or --offline for no model calls.")
            return 1
        # 20 requests a minute: run one at a time rather than tripping it.
        args.concurrency = 1

    print(f"Running {len(rows)} questions ({mode})...")

    semaphore = asyncio.Semaphore(1 if args.offline else args.concurrency)

    async def guarded(row: dict[str, Any]) -> QuestionResult:
        async with semaphore:
            if args.offline:
                return await run_offline(row)
            return await run_one(row, use_rubric=args.rubric)

    results: list[QuestionResult] = []
    for index, task in enumerate(asyncio.as_completed([guarded(r) for r in rows]), start=1):
        results.append(await task)
        if index % 10 == 0 or index == len(rows):
            print(f"  {index}/{len(rows)}")

    summary = summarise(results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "summary": summary,
        "results": [
            {
                "id": r.question_id,
                "question": r.question,
                "answer": r.answer,
                "overall": r.overall,
                "passed": r.passed,
                "failures": r.failures,
                "resources": r.resources,
                "affiliates": r.affiliates,
                "scores": [{"name": s.name, "value": s.value, "passed": s.passed, "detail": s.detail}
                           for s in r.scores],
            }
            for r in results
        ],
    }

    path = args.out or REPORTS / f"eval-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1))

    print_report(summary, results, show_failures=5)
    if args.compare and args.compare.exists():
        compare(report, args.compare)
    print(f"\nReport written to {path}")

    # Non-zero exit on a bad run so CI can gate on it.
    return 0 if summary["pass_rate"] >= 0.7 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
