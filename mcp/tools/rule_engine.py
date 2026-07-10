"""
rule_engine.py

Loads danger_signs.json and combination_rules.json, and evaluates a
structured set of infant signs against the IMNCI rule table.

Design principle: every classification returned must be traceable back
to a specific rule_id and chart_section from the source guideline.
Nothing here uses model/LLM judgment for the clinical decision itself —
that's the whole point of grounding this in a retrieval tool instead of
model memory.
"""

import json
import os
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "imnci_rules")


def _load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class RuleEngine:
    def __init__(self):
        self.signs_schema = _load_json("danger_signs.json")
        self.rules_data = _load_json("combination_rules.json")
        self.rules = self.rules_data["rules"]
        self.universal_return_signs = self.rules_data.get("universal_return_now_signs", {})

    @staticmethod
    def _sign_matches(patient_signs: dict, condition: dict) -> bool:
        """A condition like {'feeding': 'not_able_to_feed_at_all'} matches
        if patient_signs['feeding'] == 'not_able_to_feed_at_all'."""
        for key, expected in condition.items():
            if key == "note":
                continue
            if patient_signs.get(key) != expected:
                return False
        return True

    def _matches_any_of(self, patient_signs: dict, conditions: list) -> bool:
        return any(self._sign_matches(patient_signs, c) for c in conditions)

    def _matches_all_of(self, patient_signs: dict, conditions: list) -> bool:
        return all(self._sign_matches(patient_signs, c) for c in conditions)

    def _matches_count_at_least(self, patient_signs: dict, conditions: list, threshold: int) -> bool:
        count = sum(1 for c in conditions if self._sign_matches(patient_signs, c))
        return count >= threshold

    def _matches_requires(self, patient_signs: dict, requires: Optional[dict]) -> bool:
        if not requires:
            return True
        return self._sign_matches(patient_signs, requires)

    def _eval_bacterial_infection_none(self, patient_signs: dict) -> bool:
        severe_rule = self._get_rule("bacterial_infection_severe")
        local_rule = self._get_rule("bacterial_infection_local")
        has_severe = self._rule_matches(severe_rule, patient_signs)
        has_local = self._rule_matches(local_rule, patient_signs)
        return not has_severe and not has_local

    def _eval_jaundice_severe_age(self, patient_signs: dict) -> bool:
        jaundice_present = patient_signs.get("jaundice_onset") in (
            "onset_before_24_hours", "onset_after_24_hours",
        )
        age = patient_signs.get("age_days")
        return jaundice_present and age is not None and age >= 14

    def _eval_jaundice_moderate_age(self, patient_signs: dict) -> bool:
        age = patient_signs.get("age_days")
        return age is not None and age < 14

    def _eval_jaundice_none(self, patient_signs: dict) -> bool:
        return patient_signs.get("jaundice_onset") == "no_jaundice"

    def _eval_dehydration_none(self, patient_signs: dict) -> bool:
        if patient_signs.get("diarrhoea_present") != "yes":
            return False
        severe = self._get_rule("dehydration_severe")
        some = self._get_rule("dehydration_some")
        has_severe = self._matches_count_at_least(
            patient_signs, severe["signs_from"], severe["signs_count_at_least"]
        )
        has_some = self._matches_count_at_least(
            patient_signs, some["signs_from"], some["signs_count_at_least"]
        )
        return not has_severe and not has_some

    def _eval_feeding_no_problem(self, patient_signs: dict) -> bool:
        if patient_signs.get("weight_status") != "normal_weight":
            return False
        problem_rule = self._get_rule("feeding_problem_or_low_weight")
        return not self._matches_any_of(patient_signs, problem_rule["signs_any_of"])

    _SPECIAL_EVALUATORS = {
        "bacterial_infection_none": "_eval_bacterial_infection_none",
        "jaundice_severe_age_trigger": "_eval_jaundice_severe_age", 
        "jaundice_moderate": "_eval_jaundice_moderate_age",
        "jaundice_none": "_eval_jaundice_none",
        "dehydration_none": "_eval_dehydration_none",
        "feeding_no_problem": "_eval_feeding_no_problem",
    }

    def _get_rule(self, rule_id: str) -> dict:
        for r in self.rules:
            if r["id"] == rule_id:
                return r
        raise KeyError(f"Rule id not found: {rule_id}")

    def _rule_matches(self, rule: dict, patient_signs: dict) -> bool:
        rule_id = rule["id"]

        if rule_id == "jaundice_severe":
            explicit_conditions = [c for c in rule["signs_any_of"] if "condition" not in c]
            if self._matches_any_of(patient_signs, explicit_conditions):
                return True
            return self._eval_jaundice_severe_age(patient_signs)

        if rule_id in self._SPECIAL_EVALUATORS:
            method_name = self._SPECIAL_EVALUATORS[rule_id]
            base_match = getattr(self, method_name)(patient_signs)
            if rule_id == "jaundice_moderate":
                explicit = [c for c in rule["signs_all_of"] if "condition" not in c]
                return self._matches_all_of(patient_signs, explicit) and base_match
            return base_match

        if rule_id == "bacterial_infection_severe":
            if self._matches_any_of(patient_signs, rule["signs_any_of"]):
                return True
            age = patient_signs.get("age_days")
            if age is not None and age < 7 and patient_signs.get("breathing_rate") == "fast_breathing":
                return True
            return False

        if rule_id == "bacterial_infection_local":
            if not self._matches_requires(patient_signs, rule.get("requires")):
                return False
            non_breathing_conditions = [
                c for c in rule["signs_any_of"] if "breathing_rate" not in c
            ]
            if self._matches_any_of(patient_signs, non_breathing_conditions):
                return True
            age = patient_signs.get("age_days")
            if age is not None and 7 <= age <= 59:
                breathing_condition = [c for c in rule["signs_any_of"] if "breathing_rate" in c]
                return self._matches_any_of(patient_signs, breathing_condition)
            return False

        if "signs_any_of" in rule:
            if not self._matches_requires(patient_signs, rule.get("requires")):
                return False
            return self._matches_any_of(patient_signs, rule["signs_any_of"])

        if "signs_all_of" in rule:
            if not self._matches_requires(patient_signs, rule.get("requires")):
                return False
            return self._matches_all_of(patient_signs, rule["signs_all_of"])

        if "signs_count_at_least" in rule:
            if not self._matches_requires(patient_signs, rule.get("requires")):
                return False
            return self._matches_count_at_least(
                patient_signs, rule["signs_from"], rule["signs_count_at_least"]
            )

        return False

    def evaluate(self, patient_signs: dict) -> list:
        """Returns every matching rule, in the priority order defined in
        combination_rules.json's _meta.usage (bacterial infection first,
        then jaundice, diarrhoea, feeding)."""
        matches = []
        for rule in self.rules:
            if self._rule_matches(rule, patient_signs):
                matches.append({
                    "rule_id": rule["id"],
                    "chart_section": rule.get("chart_section"),
                    "classification": rule["classification"],
                    "urgency": rule["urgency"],
                    "action_summary": rule["action_summary"],
                })
        return matches