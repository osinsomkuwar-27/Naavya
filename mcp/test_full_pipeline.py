"""
test_full_pipeline.py

Tests the enhanced MCP layer end-to-end: validation catches bad input,
imnci_lookup classifies, referral_generate produces messages, log_write
persists an anonymized record (and refuses personal data).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from tools.imnci_lookup import imnci_lookup
from tools.referral_generate import referral_generate
from tools.log_write import log_write, mark_followup
from tools.validator import validate_signs


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# --- Test 1: Validation catches typos/bad values ---
section("TEST 1: Validation catches invalid input")
bad_signs = {"feeding": "not_feeding_at_all_TYPO", "breathing_rate": "fast_breathing"}
v = validate_signs(bad_signs)
print(f"Valid: {v['valid']}")
print(f"Errors: {v['errors']}")
assert v["valid"] is False, "Expected validation to catch the typo'd value"

# --- Test 2: imnci_lookup refuses to classify invalid input ---
section("TEST 2: imnci_lookup refuses invalid input (fail loud, not silent)")
result = imnci_lookup(bad_signs, source="parent_reported")
print(f"Highest urgency: {result['highest_urgency']}")
assert result["highest_urgency"] == "invalid_input"
assert result["classifications"] == []

# --- Test 3: Unknown key gets a warning but doesn't hard-fail if rest is valid ---
section("TEST 3: Unknown key warns but valid signs still classify")
mixed_signs = {
    "feeding": "not_able_to_feed_at_all",
    "breathing_rate": "fast_breathing",
    "age_days": 5,
    "totally_made_up_field": "xyz",
}
result = imnci_lookup(mixed_signs, source="asha_reported")
print(f"Highest urgency: {result['highest_urgency']}")
print(f"Validation warnings: {result['validation']['warnings']}")
assert result["highest_urgency"] == "refer_now", "Valid signs should still classify despite an unrelated unknown key"
assert result["validation"]["valid"] is True

# --- Test 4: Full happy path — Bihar mother scenario end-to-end ---
section("TEST 4: Full pipeline — Bihar mother scenario")
signs = {
    "feeding": "not_able_to_feed_at_all",
    "breathing_rate": "fast_breathing",
    "age_days": 6,
}
lookup_result = imnci_lookup(signs, source="parent_reported")
print(f"Lookup urgency: {lookup_result['highest_urgency']}")

messages = referral_generate(lookup_result)
print(f"Caregiver message: {messages['caregiver_message']}")
print(f"ASHA alert: {messages['asha_alert']}")
assert messages["asha_alert"] is not None, "refer_now should always produce an ASHA alert"

log_result = log_write(signs, lookup_result, source="parent_reported", language="odia")
print(f"Log written: {log_result['written']}, record_id: {log_result['record_id']}")
assert log_result["written"] is True

# --- Test 5: log_write refuses personal data ---
section("TEST 5: log_write refuses personal identifiers")
unsafe_signs = {"feeding": "not_able_to_feed_at_all", "name": "Radha", "phone": "9876543210"}
log_result = log_write(unsafe_signs, lookup_result, source="parent_reported")
print(f"Written: {log_result['written']}")
print(f"Error: {log_result['error']}")
assert log_result["written"] is False, "log_write must refuse when personal identifiers are present"

# --- Test 6: reassure case still gets universal return-signs appended ---
section("TEST 6: Reassure case includes universal safety-net line")
normal_signs = {
    "feeding": "feeding_normally",
    "breathing_rate": "normal",
    "jaundice_onset": "no_jaundice",
    "weight_status": "normal_weight",
}
lookup_result = imnci_lookup(normal_signs, source="asha_reported")
messages = referral_generate(lookup_result)
print(f"Caregiver message: {messages['caregiver_message']}")
assert "return immediately" in messages["caregiver_message"].lower()
assert messages["asha_alert"] is None, "reassure should NOT produce an ASHA alert"

# --- Test 7: mark_followup closes the loop ---
section("TEST 7: mark_followup updates a logged record")
signs2 = {"feeding": "not_able_to_feed_at_all", "age_days": 8}
lookup2 = imnci_lookup(signs2, source="asha_reported")
log2 = log_write(signs2, lookup2, source="asha_reported", language="hindi")
followup = mark_followup(log2["record_id"], completed=True, notes="ASHA confirmed family reached PHC same day")
print(f"Follow-up updated: {followup['updated']}")
assert followup["updated"] is True

print("\n" + "=" * 60)
print("ALL PIPELINE TESTS PASSED")
print("=" * 60)