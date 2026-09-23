"""Golden-set regression gate for answer quality.

The unit tests pin the mechanics -- that a citation resolves, that a threshold
is applied, that a correction is stored. None of them can fail when the system
starts answering questions it should route, or routes questions it can answer.
That is the failure users actually experience, and it is what this measures.

Each case in golden.yaml states the outcome the corpus justifies:

    expect: answered | routed        the answer-vs-route decision
    must_cite:                       source paths the citations must include
    must_mention:                    strings the answer must contain
    must_not_mention:                strings that would mean a wrong answer
    route_to:                        the person a routed query should reach
    routes_to_nobody: true           no one in the corpus owns this question
    requires: llm                    only the model can decide this one

`requires: llm` is not an excuse. It marks the cases that separate the two
backends -- questions whose sources discuss the subject at length without
answering it. The extractive fallback returns the best passage and calls it an
answer, so it cannot get these right, and pretending otherwise by loosening the
assertion would hide exactly the thing worth measuring. Offline runs report them
as excluded and the summary prints both counts.

    python -m eval.run_eval                 # whichever backend is configured
    python -m eval.run_eval --offline       # no API key, what CI runs
    python -m eval.run_eval --json out.json

Run it against a database ingested the same way the gate will ingest it. A
heuristic-enriched corpus scores its sources differently from a Claude-enriched
one, so a gate tuned on a local LLM ingest will disagree with CI for reasons
that have nothing to do with the change under test.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT, settings
from app.db.connection import get_connection

GOLDEN_PATH = Path(__file__).parent / "golden.yaml"


@dataclass
class CaseResult:
    id: str
    question: str
    expect: str
    got: str
    confidence: float
    failures: list[str] = field(default_factory=list)
    excluded: bool = False
    blind_spot: str | None = None
    person: str | None = None
    citations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures and not self.excluded


def _check(case: dict, outcome, backend: str) -> list[str]:
    failures: list[str] = []
    got = "routed" if outcome.routing is not None or outcome.answer is None else "answered"
    expect = case["expect"]

    if got != expect:
        failures.append(f"expected {expect}, got {got}")

    cited = [citation["source_path"] for citation in outcome.citations]
    shown = ", ".join(cited) or "none"
    for fragment in case.get("must_cite", []):
        if not any(fragment in path for path in cited):
            failures.append(f"no citation matching {fragment!r} (cited: {shown})")

    # must_cite_any is for facts more than one document states properly. The
    # Northgate root cause is in an 8D report, a transcript, bridge minutes and
    # a status-deck closure slide; citing the slide is not worse than citing the
    # report, and a gate that insists on one of them pins a preference nobody
    # decided rather than a property of the answer.
    alternatives = case.get("must_cite_any", [])
    if alternatives and not any(f in path for f in alternatives for path in cited):
        failures.append(f"no citation matching any of {alternatives} (cited: {shown})")

    # Content assertions are for synthesised prose only. The extractive backend
    # returns the best-matching passage verbatim, so "does the answer state the
    # number" is a question about that passage, not about the system -- checking
    # it offline would measure chunk boundaries. The decision, the citations and
    # the routee are checked on both backends because no model touches them.
    answer = (outcome.answer or "").lower()
    if expect == "answered" and backend == "llm":
        for phrase in case.get("must_mention", []):
            if str(phrase).lower() not in answer:
                failures.append(f"answer omits {phrase!r}")
        for phrase in case.get("must_not_mention", []):
            if str(phrase).lower() in answer:
                failures.append(f"answer contains {phrase!r}")

    if expect == "routed":
        person = outcome.routing["person"] if outcome.routing else None
        if case.get("routes_to_nobody"):
            if person is not None:
                failures.append(f"expected no routee, got {person}")
        elif "route_to" in case:
            if person != case["route_to"]:
                failures.append(f"expected routing to {case['route_to']}, got {person or 'nobody'}")

    return failures


def validate(cases: list[dict]) -> None:
    """Every exclusion has to say what it hides.

    `requires: llm` is the only way a case leaves the offline gate, and an
    unexplained one is indistinguishable from a case someone excluded because
    it was failing. Two of the five exclusions here turned out to pass offline
    all along, and a third was labelled model-only when its actual problem was
    that the extractive path cites a stale source -- neither was visible while
    the report said "5 skipped" and nothing else.
    """
    missing = [c["id"] for c in cases if c.get("requires") == "llm" and not c.get("blind_spot")]
    if missing:
        raise SystemExit(
            "these cases are excluded from the offline gate without naming what that "
            "leaves untested; add a blind_spot: " + ", ".join(missing)
        )


def run(cases: list[dict], db_path: Path | None = None) -> list[CaseResult]:
    from app.query.service import answer_query

    backend = "llm" if settings.has_api_key else "extractive"
    offline = backend != "llm"
    conn = get_connection(db_path)
    results: list[CaseResult] = []
    try:
        for case in cases:
            if offline and case.get("requires") == "llm":
                results.append(
                    CaseResult(
                        id=case["id"], question=case["question"], expect=case["expect"],
                        got="-", confidence=0.0, excluded=True,
                        blind_spot=case["blind_spot"],
                    )
                )
                continue

            outcome = answer_query(conn, case["question"])
            got = "routed" if outcome.routing is not None or outcome.answer is None else "answered"
            results.append(
                CaseResult(
                    id=case["id"],
                    question=case["question"],
                    expect=case["expect"],
                    got=got,
                    confidence=outcome.confidence,
                    failures=_check(case, outcome, backend),
                    person=outcome.routing["person"] if outcome.routing else None,
                    citations=[c["source_path"] for c in outcome.citations],
                )
            )
    finally:
        conn.close()
    return results


def _bands(results: list[CaseResult]) -> dict:
    """Where the two outcomes actually sit relative to the routing threshold.

    A gate that only counts passes hides the margin. If the answered band's
    floor drifts down towards the threshold, the next corpus change flips a
    query with no test failing first.
    """
    answered = [r.confidence for r in results if r.got == "answered"]
    routed = [r.confidence for r in results if r.got == "routed"]
    band = {
        "threshold": settings.confidence_threshold,
        "answered": [round(min(answered), 3), round(max(answered), 3)] if answered else None,
        "routed": [round(min(routed), 3), round(max(routed), 3)] if routed else None,
    }
    band["separated"] = bool(
        answered and routed and min(answered) > settings.confidence_threshold >= max(routed)
    )

    # The number to watch across runs. Passing says nothing about how nearly a
    # case failed, and the first symptom of retrieval drift is this shrinking.
    closest = min(
        (r for r in results if r.got == "answered"), key=lambda r: r.confidence, default=None
    )
    band["narrowest_margin"] = (
        {"case": closest.id, "margin": round(closest.confidence - settings.confidence_threshold, 3)}
        if closest
        else None
    )
    return band


def _blind_spots(results: list[CaseResult]) -> dict[str, list[str]]:
    """What this run did not test, grouped by kind."""
    grouped: dict[str, list[str]] = {}
    for r in results:
        if r.excluded:
            grouped.setdefault(r.blind_spot or "unlabelled", []).append(r.id)
    return grouped


def _markdown(results: list[CaseResult], bands: dict, backend: str) -> str:
    """A GitHub step summary, so the bands are readable on the run page.

    The alternative is a log nobody opens and an artifact nobody downloads,
    which is how a margin quietly shrinking from 0.09 to 0.01 goes unnoticed
    for as long as the gate keeps passing.
    """
    passed = sum(1 for r in results if r.passed)
    excluded = sum(1 for r in results if r.excluded)
    failed = sum(1 for r in results if not r.passed and not r.excluded)
    scored = len(results) - excluded

    headline = f"{'FAILED' if failed else 'passed'} {passed}/{scored}"
    if excluded:
        headline += f", {excluded} excluded (model-only)"

    lines = [
        "### Golden-set answer-quality gate",
        "",
        f"**{headline}** &middot; backend `{backend}` "
        f"&middot; threshold {bands['threshold']}",
        "",
        "| outcome | confidence range |",
        "| --- | --- |",
    ]
    for outcome in ("answered", "routed"):
        span = bands[outcome]
        lines.append(f"| {outcome} | {f'{span[0]} - {span[1]}' if span else 'none'} |")

    lines.append("")
    if bands["separated"]:
        margin = bands["narrowest_margin"]
        lines.append(
            f"Bands are separated by the threshold. Narrowest margin above it: "
            f"**{margin['margin']}** (`{margin['case']}`)."
        )
    else:
        lines.append("**The two bands are not cleanly separated by the threshold.**")

    blind = _blind_spots(results)
    if blind:
        lines += ["", "**Not tested by this run:**"]
        for kind, ids in sorted(blind.items()):
            lines.append(f"- {kind} &mdash; " + ", ".join(f"`{i}`" for i in ids))

    lines += ["", "<details><summary>All cases</summary>", "", "| case | expect | got | confidence | |", "| --- | --- | --- | --- | --- |"]
    for r in results:
        if r.excluded:
            mark, confidence = f"skipped &mdash; {r.blind_spot} untested", "-"
        elif r.passed:
            mark, confidence = "ok", f"{r.confidence:.3f}"
        else:
            mark, confidence = "**FAIL** " + "; ".join(r.failures), f"{r.confidence:.3f}"
        lines.append(f"| `{r.id}` | {r.expect} | {r.got} | {confidence} | {mark} |")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def _report(results: list[CaseResult], bands: dict) -> None:
    width = max(len(r.id) for r in results)
    print(f"\n{'case'.ljust(width)}  expect    got       conf   ")
    print("-" * (width + 34))
    for r in results:
        if r.excluded:
            mark, detail = "skip", f"model-only: leaves {r.blind_spot} untested"
        elif r.passed:
            mark, detail = "ok  ", ""
        else:
            mark, detail = "FAIL", "; ".join(r.failures)
        print(f"{r.id.ljust(width)}  {r.expect:<9} {r.got:<9} {r.confidence:<6.3f} {mark}  {detail}")

    passed = sum(1 for r in results if r.passed)
    excluded = sum(1 for r in results if r.excluded)
    failed = sum(1 for r in results if not r.passed and not r.excluded)
    scored = len(results) - excluded

    print(f"\n{passed}/{scored} passed" + (f", {excluded} excluded (model-only)" if excluded else ""))
    for kind, ids in sorted(_blind_spots(results).items()):
        print(f"untested: {kind:<24} {', '.join(ids)}")
    print(
        f"confidence  answered {bands['answered']}  routed {bands['routed']}  "
        f"threshold {bands['threshold']}"
    )
    margin = bands["narrowest_margin"]
    if margin:
        print(f"narrowest margin above the threshold  {margin['margin']}  ({margin['case']})")
    if not bands["separated"]:
        print("  note: the two bands are not cleanly separated by the threshold")
    if failed:
        print(f"\n{failed} regression(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the golden-set answer-quality gate.")
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument(
        "--offline", action="store_true",
        help="Ignore any configured API key and use the extractive backend (what CI runs).",
    )
    parser.add_argument("--json", type=Path, default=None, help="Also write results as JSON.")
    parser.add_argument(
        "--markdown", type=Path, default=None,
        help="Append a markdown summary to this file (CI passes $GITHUB_STEP_SUMMARY).",
    )
    parser.add_argument(
        "--require-llm", action="store_true",
        help="Fail unless the model backend is actually in use. For the scheduled gate.",
    )
    args = parser.parse_args()

    if args.offline:
        settings.anthropic_api_key = ""

    # Without this, a scheduled run whose secret has expired, been renamed or
    # never reached the runner falls back to the extractive backend, skips the
    # three model-only cases, reports 16/16 and goes green -- a gate whose
    # entire purpose is to exercise the model, passing without calling it. A
    # capability check that does not exercise the capability is not a check.
    if args.require_llm and not settings.has_api_key:
        raise SystemExit(
            "--require-llm was passed but no ANTHROPIC_API_KEY is configured, so this "
            "run would silently grade the extractive backend instead of the model. "
            "Check that the repository secret exists and is exposed to this job."
        )

    cases = yaml.safe_load(args.golden.read_text(encoding="utf-8"))["cases"]
    validate(cases)
    backend = "llm" if settings.has_api_key else "extractive"
    db = args.db or settings.db_path
    print(f"golden set: {len(cases)} cases | backend: {backend} | db: {db}")
    if not Path(db).exists():
        print(f"\nNo database at {db}. Run: python -m app.ingestion.pipeline --reset --no-llm")
        return 2

    results = run(cases, db_path=args.db)
    bands = _bands(results)
    _report(results, bands)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "backend": backend,
                    "bands": bands,
                    "cases": [
                        {
                            "id": r.id, "expect": r.expect, "got": r.got,
                            "confidence": r.confidence, "excluded": r.excluded,
                            "failures": r.failures, "person": r.person,
                            "citations": r.citations,
                        }
                        for r in results
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json.relative_to(PROJECT_ROOT) if args.json.is_absolute() else args.json}")

    if args.markdown:
        # Appended, not written: $GITHUB_STEP_SUMMARY accumulates across steps.
        with args.markdown.open("a", encoding="utf-8") as handle:
            handle.write(_markdown(results, bands, backend))

    return 1 if any(not r.passed and not r.excluded for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
