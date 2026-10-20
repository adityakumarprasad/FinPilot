"""Judge calibration: does the LLM judge agree with a human?

Usage:  uv run python -m evaluation.run_calibration          (add --show to print every report)
"""
import argparse
import json
import os
import re
import sys

import numpy as np

from app import config, judge, llm

HERE = os.path.join(os.path.dirname(__file__), "judge_calibration")
RESULTS_FILE = os.path.join(HERE, "results.md")


def build_report(base: str, case: dict) -> str:
    report = base
    for old, new in case.get("edits", []):
        if old not in report:
            raise ValueError(f"Case '{case['id']}': text to replace not found: {old[:40]}...")
        report = report.replace(old, new)
    for section in case.get("remove_sections", []):
        report = re.sub(rf"## {section}\n.*?(?=\n## |\Z)", "", report, flags=re.DOTALL)
    return report.strip() + "\n"


def calibration_metrics(human: list[float], judged: list[float]) -> dict:
    h, j = np.array(human, dtype=float), np.array(judged, dtype=float)
    correlation = float(np.corrcoef(h, j)[0, 1]) if h.std() and j.std() else 0.0
    return {
        "mean_absolute_error": float(np.mean(np.abs(h - j))),        # average points of disagreement
        "correlation": correlation,                                   # do they RANK reports the same way?
        "pass_fail_agreement": float(np.mean((h >= config.PASS_SCORE) == (j >= config.PASS_SCORE))),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="print each generated report")
    args = parser.parse_args()

    with open(os.path.join(HERE, "facts.json"), encoding="utf-8") as f:
        facts = json.load(f)
    with open(os.path.join(HERE, "base_report.md"), encoding="utf-8") as f:
        base = f.read()
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)

    rows, human, judged = [], [], []
    for case in cases:
        report = build_report(base, case)
        if args.show:
            print(f"\n===== {case['id']} =====\n{report}")
        verdict = judge.judge(facts, report)
        if llm.stats["quota_exhausted"]:
            print("STOPPED: the LLM daily quota is used up. No results written. Re-run later (answers are cached).")
            sys.exit(1)
        human.append(case["human_score"])
        judged.append(verdict["score"])
        gap = verdict["score"] - case["human_score"]
        flag = " ⚠️" if abs(gap) >= 3 else ""
        rows.append(f"| {case['id']} | {case['defect']} | {case['human_score']} | {verdict['score']} | {gap:+d}{flag} "
                    f"| {verdict['reasoning'][:120]} |")

    m = calibration_metrics(human, judged)
    text = "\n".join([
        "# Judge calibration results", "",
        f"Model: `{config.LLM_MODEL}` · judge version `{config.PROMPT_VERSION}` · {len(cases)} reports", "",
        "| Metric | Value | Meaning |", "|---|---|---|",
        f"| Mean absolute error | {m['mean_absolute_error']:.1f} points | average disagreement on a 0–10 scale |",
        f"| Correlation | {m['correlation']:.2f} | 1.0 = ranks reports exactly like the human |",
        f"| Pass/fail agreement | {m['pass_fail_agreement']:.0%} | same decision on 'good enough' ({config.PASS_SCORE}+) |",
        "", "| Case | Defect | Human | Judge | Gap | Judge's reasoning |", "|---|---|---|---|---|---|", *rows,
        "", "⚠️ = disagreement of 3+ points: read these, then improve the judge rubric and re-run.",
    ])
    print("\n" + text)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    _log_scores(m)
    llm.flush()


def _log_scores(m: dict):
    """Send the calibration metrics to Langfuse so judge prompt versions can be compared over time."""
    if config.LANGFUSE_ENABLED:
        from langfuse import get_client
        meta = {"model": config.LLM_MODEL, "prompt_version": config.PROMPT_VERSION}
        for name, value in m.items():
            get_client().score_current_trace(name=f"judge_{name}", value=value, metadata=meta)


if config.LANGFUSE_ENABLED:
    from langfuse import observe
    main = observe(name="judge-calibration")(main)


if __name__ == "__main__":
    main()
