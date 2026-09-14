import tempfile
import unittest
from pathlib import Path

from odf_schema import EVIDENCE_CONFIDENCE, LOADER_RULES, SCHEMA_VERSION
from odf_validator import validate_directory


class ODFProvenanceTests(unittest.TestCase):
    def rule(self, rule_id):
        return next(rule for rule in LOADER_RULES if rule.rule_id == rule_id)

    def test_schema_version_tracks_provenance_model(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 3)

    def test_flare_rule_has_concrete_crash_chain_provenance(self):
        flare = self.rule("flare-mine")
        by_symbol = {e.symbol: e for e in flare.evidence if e.symbol}

        self.assertEqual("0x004D2B10", by_symbol["FlareMineClass::Load"].address)
        self.assertEqual("0x004D2E90", by_symbol["FlareMine::Update(float)"].address)
        self.assertEqual("0x00586FF0", by_symbol["OrdnanceClass::Build"].address)
        self.assertTrue(any("0x00586FFC" in e.summary for e in flare.evidence))

    def test_curated_evidence_uses_declared_confidence_vocabulary(self):
        allowed = set(EVIDENCE_CONFIDENCE)
        for rule in LOADER_RULES:
            for evidence in rule.evidence:
                self.assertIn(evidence.confidence, allowed)

    def test_inferred_evidence_is_not_used_by_current_hard_rules(self):
        for rule in LOADER_RULES:
            self.assertFalse(any(e.confidence == "inferred" for e in rule.evidence))

    def test_flame_delay_is_reported_as_dead_spelling(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "flame.odf").write_text(
                """
[OrdnanceClass]
classLabel = "flamepuff"
[FlamePuffClass]
flameDelay = 0.1
""",
                encoding="latin-1",
                newline="\r\n",
            )
            issues = validate_directory(root)
            matches = [i for i in issues if i.rule_id == "flame-puff" and i.key == "flameDelay"]
            self.assertEqual(1, len(matches))
            self.assertIn("frameDelay", matches[0].suggestion)


if __name__ == "__main__":
    unittest.main()
