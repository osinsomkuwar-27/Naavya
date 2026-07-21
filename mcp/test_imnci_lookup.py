"""
test_imnci_lookup.py

Sanity tests using the exact scenarios discussed in the pitch — the Bihar
mother (should refer_now) and the Karnataka father (should reassure/monitor).
Run with: python test_imnci_lookup.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from tools.imnci_lookup import imnci_lookup


def run_case(name, signs, source="parent_reported"):
    print(f"\n{'=' * 60}\nCASE: {name}\n{'=' * 60}")
    result = imnci_lookup(signs, source=source)
    print(f"Highest urgency: {result['highest_urgency']}")
    print(f"Matched rules:   {result['matched_rule_ids']}")
    print(f"Action summary:  {result['action_summary']}")
    if result["confidence_note"]:
        print(f"Confidence note: {result['confidence_note']}")
    return result


# Case 1: Bihar mother — not feeding at all + fast breathing -> refer_now
r1 = run_case("Bihar mother — feeding + breathing combo", {
    "feeding": "not_able_to_feed_at_all",
    "breathing_rate": "fast_breathing",
    "age_days": 6,
})
assert r1["highest_urgency"] == "refer_now", "Expected refer_now for danger combo"

# Case 2: Karnataka father — mild face-only jaundice, day 10, normal feeding
r2 = run_case("Karnataka father — mild jaundice, day 10, normal feeding", {
    "jaundice_onset": "onset_after_24_hours",
    "jaundice_extent": "face_or_body_only",
    "age_days": 10,
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
})
print(f"(Expect monitor_recheck, not full reassure, since input is parent_reported)")

# Case 3: Same jaundice pattern but infant is now 14 days old -> should flip to refer_now
r3 = run_case("Same pattern but infant now 14 days old", {
    "jaundice_onset": "onset_after_24_hours",
    "jaundice_extent": "face_or_body_only",
    "age_days": 14,
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
})
assert r3["highest_urgency"] == "refer_now", "Expected refer_now once age >= 14 days with jaundice present"

# Case 4: Truly clean case — no signs at all, ASHA-reported (should reassure, no wider margin applied)
r4 = run_case("Fully normal newborn, ASHA-reported", {
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
    "jaundice_onset": "no_jaundice",
    "diarrhoea_present": "no",
    "weight_status": "normal_weight",
}, source="asha_reported")
assert r4["highest_urgency"] == "reassure", "Expected reassure for a genuinely clean ASHA-reported case"
assert r4["confidence_note"] is None, "ASHA-reported input should not get the parent safety margin"

# Case 5: Severe pustules -> should escalate to refer_now, not stay local
r5 = run_case("10+ skin pustules -> should escalate to severe", {
    "skin_pustules": "ten_or_more_or_big_boil",
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
})
assert r5["highest_urgency"] == "refer_now", "Expected refer_now for severe pustule count"

# Case 6: Few localized pustules -> should stay monitor, not escalate
r6 = run_case("Few localized pustules -> should stay monitor", {
    "skin_pustules": "few_localized",
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
})
assert r6["highest_urgency"] == "monitor_recheck", "Expected monitor_recheck for few localized pustules"

# Case 7: Bihar mother, age 6 days -> fast_breathing should ONLY match severe,
# not also match local infection (that rule requires age 7-59 days)
r7 = run_case("Bihar mother re-check: age 6 days, should NOT double-match local", {
    "feeding": "not_able_to_feed_at_all",
    "breathing_rate": "fast_breathing",
    "age_days": 6,
})
assert r7["highest_urgency"] == "refer_now"
assert "bacterial_infection_local" not in r7["matched_rule_ids"], (
    "fast_breathing at age 6 days should not trigger the local infection rule"
)

# Case 8: Fast breathing ALONE (no other severe signs), age 10 days ->
# should match ONLY local infection (monitor), NOT severe (refer_now),
# since fast_breathing only means "severe" under 7 days old.
r8 = run_case("Fast breathing alone, age 10 days -> local infection only", {
    "feeding": "feeding_normally",
    "breathing_rate": "fast_breathing",
    "age_days": 10,
})
assert "bacterial_infection_local" in r8["matched_rule_ids"], (
    "fast_breathing at age 10 days should trigger local infection rule"
)
assert "bacterial_infection_severe" not in r8["matched_rule_ids"], (
    "fast_breathing at age 10 days should NOT trigger severe classification"
)
assert r8["highest_urgency"] == "monitor_recheck"

# Case 9: Fast breathing alone, age 4 days -> SHOULD trigger severe (refer_now),
# and should NOT also trigger local (which requires 7-59 days)
r9 = run_case("Fast breathing alone, age 4 days -> severe only", {
    "feeding": "feeding_normally",
    "breathing_rate": "fast_breathing",
    "age_days": 4,
})
assert "bacterial_infection_severe" in r9["matched_rule_ids"]
assert "bacterial_infection_local" not in r9["matched_rule_ids"], (
    "fast_breathing at age 4 days should NOT trigger local infection rule"
)
assert r9["highest_urgency"] == "refer_now"

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)