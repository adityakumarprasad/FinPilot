"""Red-team the input guardrail: attack block rate vs false block rate, per guardrail configuration.

Usage:  uv run python -m evaluation.run_redteam
"""
import os
import sys

from app import config, guardrails, llm

HERE = os.path.dirname(__file__)
RESULTS_FILE = os.path.join(HERE, "redteam", "results.md")
CONFIGS = {  # label: (use_regex, use_llm)
    "Regex only": (True, False),
    "AI classifier only": (False, True),
    "Regex + AI classifier": (True, True),
}


def load_lines(name: str) -> list[str]:
    with open(os.path.join(HERE, "redteam", name), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def rate(results: list[bool]) -> float:
    return sum(results) / len(results) if results else 0.0


def run_config(texts: list[str], use_regex: bool, use_llm: bool) -> list[bool]:
    blocked = []
    for text in texts:
        blocked.append(guardrails.check_input(text, use_regex, use_llm)[0])
        if llm.stats["quota_exhausted"]:
            # a failed classifier "blocks to be safe", which would fake great attack numbers: stop instead
            print("STOPPED: the LLM daily quota is used up. No results written. Re-run later (answers are cached).")
            sys.exit(1)
    return blocked


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    attacks, benign = load_lines("attacks.txt"), load_lines("benign.txt")
    lines = ["# Guardrail red-team results", "",
             f"Model: `{config.LLM_MODEL}` · {len(attacks)} attacks · {len(benign)} normal requests", "",
             "| Guardrail | Attacks blocked (higher = better) | Normal requests wrongly blocked (lower = better) |",
             "|---|---|---|"]
    details = []
    for label, (use_regex, use_llm) in CONFIGS.items():
        print(f"Running: {label} ...")
        attack_blocked = run_config(attacks, use_regex, use_llm)
        benign_blocked = run_config(benign, use_regex, use_llm)
        lines.append(f"| {label} | {rate(attack_blocked):.0%} ({sum(attack_blocked)}/{len(attacks)}) "
                     f"| {rate(benign_blocked):.0%} ({sum(benign_blocked)}/{len(benign)}) |")
        missed = [f"- {t}" for t, b in zip(attacks, attack_blocked) if not b] or ["- none"]
        false_blocks = [f"- {t}" for t, b in zip(benign, benign_blocked) if b] or ["- none"]
        details += ["", f"### {label}", "**Attacks that got through:**", *missed,
                    "**Normal requests wrongly blocked:**", *false_blocks]
        _log_scores(label, rate(attack_blocked), rate(benign_blocked))

    text = "\n".join(lines + ["", "## Details"] + details)
    print("\n" + text)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    llm.flush()


def _log_scores(label: str, attack_rate: float, false_rate: float):
    """Send the numbers to Langfuse so guardrail versions can be compared over time."""
    if config.LANGFUSE_ENABLED:
        from langfuse import get_client
        key = label.lower().replace(" + ", "_").replace(" ", "_")          # e.g. "regex_ai_classifier"
        meta = {"guardrail": label, "model": config.LLM_MODEL, "prompt_version": config.PROMPT_VERSION}
        get_client().score_current_trace(name=f"attack_block_rate.{key}", value=attack_rate, metadata=meta)
        get_client().score_current_trace(name=f"false_block_rate.{key}", value=false_rate, metadata=meta)


if config.LANGFUSE_ENABLED:
    from langfuse import observe
    main = observe(name="redteam-run")(main)


if __name__ == "__main__":
    main()
