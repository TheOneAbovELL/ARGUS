"""Regression gate: the offline research evaluation must keep its guarantees."""

from evals.research_eval import run


def test_research_eval_guarantees_hold() -> None:
    summary = run(["deterministic", "faithful", "hallucinating", "injected", "outage", "malformed"])["scenarios"]
    for name, s in summary.items():
        assert s["schema_ok"], name
        assert s["citation_validity"] == 1.0, name
        assert s["numeric_fidelity"] == 1.0, name
        assert s["facts_cited"] == 1.0, name
        assert s["metric_fidelity"], name
        assert s["bad_claims_shown"] == 0, name
    assert summary["hallucinating"]["rejected_by_validator"] >= 3 * 4  # every planted claim caught
    assert summary["injected"]["rejected_by_validator"] >= 4
    assert summary["faithful"]["modes"] == ["llm"]
    assert summary["outage"]["fallback_ok"] and summary["malformed"]["fallback_ok"]
    assert summary["deterministic"]["consistent"] and summary["faithful"]["consistent"]
