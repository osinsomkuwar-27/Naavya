"""
run_bias_tests.py

Executes ethics/bias_report/test_cases.json against the real
mcp/tools/imnci_lookup.py classification logic, and generates a
results summary used in bias_report.md.

Run with: python3 run_bias_tests.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))
from tools.imnci_lookup import imnci_lookup  # noqa: E402

TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")

PROHIBITED_ATTRIBUTE_KEYWORDS = [
    "gender", "sex", "caste", "religion", "name", "ethnicity", "race",
    "region", "language", "income", "wealth", "class", "tribe", "surname",
]


def load_test_cases():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_demographic_neutrality():
    """Static scan of danger_signs.json for any prohibited attribute keys."""
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "imnci_rules", "danger_signs.json"
    )
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    all_keys = list(schema.get("signs", {}).keys())
    flagged = []
    for key in all_keys:
        for bad_word in PROHIBITED_ATTRIBUTE_KEYWORDS:
            if bad_word in key.lower():
                flagged.append(key)

    return {
        "total_sign_fields": len(all_keys),
        "all_fields": all_keys,
        "flagged_fields": flagged,
        "passed": len(flagged) == 0,
    }


def check_determinism(cases):
    results = []
    for case in cases:
        outputs = []
        for _ in range(case["repeat_count"]):
            result = imnci_lookup(case["signs"], source=case["source"])
            outputs.append(json.dumps(result, sort_keys=True))
        all_identical = len(set(outputs)) == 1
        results.append({
            "id": case["id"],
            "repeat_count": case["repeat_count"],
            "all_identical": all_identical,
            "passed": all_identical,
        })
    return results


def check_source_fairness(cases):
    results = []
    for case in cases:
        asha_result = imnci_lookup(case["signs"], source="asha_reported")
        parent_result = imnci_lookup(case["signs"], source="parent_reported")

        entry = {
            "id": case["id"],
            "description": case["description"],
            "asha_urgency": asha_result["highest_urgency"],
            "parent_urgency": parent_result["highest_urgency"],
        }

        # The core fairness invariant: parent_reported urgency must NEVER
        # be lower (less cautious) than asha_reported for the same signs.
        # It's fine (by design) for parent_reported to be equal or higher.
        urgency_rank = {"reassure": 1, "monitor_recheck": 2, "refer_now": 3,
                         "insufficient_data": 0, "invalid_input": 0}
        asha_rank = urgency_rank.get(entry["asha_urgency"], 0)
        parent_rank = urgency_rank.get(entry["parent_urgency"], 0)

        entry["passed"] = parent_rank >= asha_rank
        entry["direction"] = (
            "equal" if parent_rank == asha_rank
            else "parent_more_cautious" if parent_rank > asha_rank
            else "parent_LESS_cautious_VIOLATION"
        )
        results.append(entry)
    return results


def check_boundary_consistency(cases):
    results = []
    for case in cases:
        if "signs_few" in case:
            # pustule count boundary case has two sub-cases
            few_result = imnci_lookup(case["signs_few"], source="asha_reported")
            severe_result = imnci_lookup(case["signs_severe"], source="asha_reported")
            passed = (
                few_result["highest_urgency"] == case["expected_few"]
                and severe_result["highest_urgency"] == case["expected_severe"]
            )
            results.append({
                "id": case["id"],
                "description": case["description"],
                "few_urgency": few_result["highest_urgency"],
                "severe_urgency": severe_result["highest_urgency"],
                "passed": passed,
            })
            continue

        result = imnci_lookup(case["signs"], source="asha_reported")

        if "expected_matched_rule" in case:
            matched = case["expected_matched_rule"] in result["matched_rule_ids"]
            not_matched = case["expected_not_matched"] not in result["matched_rule_ids"]
            passed = matched and not_matched
            results.append({
                "id": case["id"],
                "description": case["description"],
                "matched_rule_ids": result["matched_rule_ids"],
                "passed": passed,
            })
        elif "expected_urgency" in case:
            passed = result["highest_urgency"] == case["expected_urgency"]
            results.append({
                "id": case["id"],
                "description": case["description"],
                "highest_urgency": result["highest_urgency"],
                "expected": case["expected_urgency"],
                "passed": passed,
            })
    return results


def main():
    test_cases = load_test_cases()

    print("=" * 70)
    print("1. DEMOGRAPHIC NEUTRALITY CHECK")
    print("=" * 70)
    neutrality = check_demographic_neutrality()
    print(json.dumps(neutrality, indent=2))

    print("\n" + "=" * 70)
    print("2. DETERMINISM CHECK")
    print("=" * 70)
    determinism = check_determinism(test_cases["determinism_cases"])
    print(json.dumps(determinism, indent=2))

    print("\n" + "=" * 70)
    print("3. SOURCE FAIRNESS CHECK")
    print("=" * 70)
    fairness = check_source_fairness(test_cases["source_fairness_cases"])
    print(json.dumps(fairness, indent=2))

    print("\n" + "=" * 70)
    print("4. BOUNDARY CONSISTENCY CHECK")
    print("=" * 70)
    boundaries = check_boundary_consistency(test_cases["boundary_consistency_cases"])
    print(json.dumps(boundaries, indent=2))

    all_results = {
        "demographic_neutrality": neutrality,
        "determinism": determinism,
        "source_fairness": fairness,
        "boundary_consistency": boundaries,
    }

    total_checks = (
        1 + len(determinism) + len(fairness) + len(boundaries)
    )
    total_passed = (
        (1 if neutrality["passed"] else 0)
        + sum(1 for r in determinism if r["passed"])
        + sum(1 for r in fairness if r["passed"])
        + sum(1 for r in boundaries if r["passed"])
    )

    print("\n" + "=" * 70)
    print(f"SUMMARY: {total_passed}/{total_checks} checks passed")
    print("=" * 70)

    output_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results written to {output_path}")

    assert total_passed == total_checks, "One or more bias/fairness checks FAILED -- see output above"
    print("\nALL BIAS/FAIRNESS CHECKS PASSED")


if __name__ == "__main__":
    main()