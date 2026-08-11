"""Tests for vanilla_core.attest.

Each class corresponds to a discipline the module exists to enforce, and each
of those exists because something already got past the checks that were there.

Run: PYTHONPATH=src python3 tests/test_attest.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vanilla_core.attest import (  # noqa: E402
    Attestor, Direction, Measure, Mutation, falsify,
)


class Box:
    """A mutable integer, so a test can move what a measure reads."""

    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value


def attestor(measures, tmp):
    return Attestor(measures=measures, baseline_path=Path(tmp) / "attest.json")


class TestDirection(unittest.TestCase):
    def test_a_measure_must_declare_a_direction(self):
        with self.assertRaises(ValueError):
            Measure("x", "sideways", Box(1))

    def test_a_capability_may_not_carry_a_population_guard(self):
        """A capability count of zero is a real finding — the capability is
        gone. Calling that vacuous would suppress exactly the alarm the
        measure exists to raise."""
        with self.assertRaises(ValueError):
            Measure("x", Direction.CAPABILITY, Box(0), population=Box(0))


class TestDefectsMayOnlyFall(unittest.TestCase):
    def test_a_defect_rising_is_a_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            self.assertEqual(a.record(), [])
            bugs.value = 5
            held, readings = a.check()
            self.assertFalse(held)
            self.assertIn("REGRESSION", readings[0].describe())

    def test_a_defect_falling_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            bugs.value = 1
            held, _ = a.check()
            self.assertTrue(held)


class TestCapabilitiesMayOnlyRise(unittest.TestCase):
    """The hole this module was built for.

    Demonstrated in ACI: deleting an entire failure corpus took the untested
    counter from 1 to 0, which a defect-only ratchet reported as an
    improvement while every readiness gate still passed."""

    def test_a_capability_falling_is_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            corpus.value = 0          # the deletion
            held, readings = a.check()
            self.assertFalse(held, "destroying a corpus was reported as fine")
            self.assertIn("REGRESSION", readings[0].describe())

    def test_a_capability_rising_is_expected_not_flagged(self):
        """Above the baseline is fine and expected. A check that failed on
        growth would punish exactly the behaviour it exists to enable."""
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            corpus.value = 40
            held, readings = a.check()
            self.assertTrue(held)
            self.assertIn("rose", readings[0].describe())

    def test_the_same_deletion_would_pass_a_defect_only_registry(self):
        """Why both directions have to exist. This is the ACI hole reproduced
        against a registry that measures only defects — it passes."""
        with tempfile.TemporaryDirectory() as tmp:
            untested = Box(1)
            a = attestor([Measure("untested", Direction.DEFECT, untested)], tmp)
            a.record()
            untested.value = 0        # by deleting the whole corpus
            held, _ = a.check()
            self.assertTrue(held, "a defect-only registry cannot see this, "
                                  "which is the entire point of Direction")


class TestSupersession(unittest.TestCase):
    def test_a_capability_may_fall_with_a_reason_and_a_witness(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            corpus.value = 8
            a.supersede("corpus", 8, reason="two entries described the same "
                        "precondition class and were merged", witness="shibbieness")
            held, _ = a.check()
            self.assertTrue(held)

    def test_a_supersession_without_reasoning_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            for blank in ("", "   "):
                with self.subTest(reason=blank):
                    with self.assertRaises(ValueError):
                        a.supersede("corpus", 8, reason=blank, witness="shibbieness")

    def test_a_supersession_without_a_witness_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            with self.assertRaises(ValueError):
                a.supersede("corpus", 8, reason="merged", witness="")

    def test_a_supersession_may_not_record_growth(self):
        """Growth never needs excusing, and allowing it here would turn the
        permission log into a general-purpose override."""
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            with self.assertRaises(ValueError):
                a.supersede("corpus", 12, reason="more", witness="shibbieness")

    def test_a_defect_cannot_be_superseded(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            with self.assertRaises(ValueError):
                a.supersede("bugs", 1, reason="x", witness="shibbieness")

    def test_the_supersession_is_written_to_disk(self):
        """The log is what makes the decrease permissible, so it has to
        outlive the process that permitted it."""
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Box(9)
            a = attestor([Measure("corpus", Direction.CAPABILITY, corpus)], tmp)
            a.record()
            a.supersede("corpus", 8, reason="merged duplicates",
                        witness="shibbieness")
            data = json.loads((Path(tmp) / "attest.json").read_text())
            self.assertEqual(len(data["supersessions"]), 1)
            self.assertEqual(data["supersessions"][0]["witness"], "shibbieness")
            self.assertIn("merged", data["supersessions"][0]["reason"])


class TestVacuity(unittest.TestCase):
    def test_a_defect_of_zero_over_an_empty_population_is_vacuous(self):
        """'No unmined failures' reads identically whether nothing failed or
        nothing is tracked."""
        with tempfile.TemporaryDirectory() as tmp:
            a = attestor([Measure("unmined", Direction.DEFECT, Box(0),
                                  population=Box(0))], tmp)
            held, readings = a.check()
            self.assertTrue(readings[0].vacuous)
            self.assertFalse(readings[0].ok, "an empty population passed")
            self.assertFalse(held)

    def test_the_same_measure_passes_once_the_population_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            pop = Box(0)
            a = attestor([Measure("unmined", Direction.DEFECT, Box(0),
                                  population=pop)], tmp)
            self.assertFalse(a.check()[0])
            pop.value = 11
            held, readings = a.check()
            self.assertFalse(readings[0].vacuous)
            self.assertTrue(held)

    def test_a_gate_cannot_be_cleared_by_emptying_what_it_measures(self):
        """The attack the guard exists to stop: satisfy the check by deleting
        the population rather than by fixing anything."""
        with tempfile.TemporaryDirectory() as tmp:
            pop, defects = Box(10), Box(4)
            a = attestor([Measure("bad", Direction.DEFECT, defects,
                                  population=pop)], tmp)
            a.record()
            pop.value, defects.value = 0, 0      # delete everything
            held, readings = a.check()
            self.assertTrue(readings[0].vacuous)
            self.assertFalse(held)


class TestBaselineHygiene(unittest.TestCase):
    def test_record_refuses_a_regression_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            bugs.value = 9
            problems = a.record()
            self.assertTrue(problems)
            self.assertIn("bugs", problems[0])

    def test_recording_a_regression_needs_an_explicit_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            bugs.value = 9
            with self.assertRaises(ValueError):
                a.record(allow_regression=True)
            self.assertEqual(a.record(allow_regression=True,
                                      reason="scope widened deliberately"), [])

    def test_a_changed_measure_set_invalidates_the_baseline(self):
        """A baseline is only comparable to readings taken under the same
        definitions. A count that falls under a different scoreboard proves
        nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(3)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            self.assertTrue(a.check()[0])
            b = attestor([Measure("bugs", Direction.DEFECT, bugs),
                          Measure("new", Direction.DEFECT, Box(0))], tmp)
            self.assertFalse(b.check()[0], "the baseline survived a scoreboard change")

    def test_an_unmeasured_quantity_is_reported_not_skipped(self):
        """A quantity nobody has a baseline for is one nobody would miss."""
        with tempfile.TemporaryDirectory() as tmp:
            a = attestor([Measure("fresh", Direction.DEFECT, Box(7))], tmp)
            _, readings = a.check()
            self.assertTrue(readings[0].unmeasured)
            self.assertIn("new measure", readings[0].describe())

    def test_history_records_what_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            bugs = Box(9)
            a = attestor([Measure("bugs", Direction.DEFECT, bugs)], tmp)
            a.record()
            bugs.value = 4
            a.record()
            data = json.loads((Path(tmp) / "attest.json").read_text())
            self.assertEqual(data["history"][-1]["changed"]["bugs"],
                             {"from": 9, "to": 4})


class TestFalsify(unittest.TestCase):
    def test_a_check_that_cannot_fail_is_reported_as_surviving(self):
        """The ACI finding, in miniature: a gate required zero collisions
        while a constraint made collisions unrepresentable."""
        results = falsify(
            checks={"impossible": lambda: True},
            mutations=[Mutation("impossible", lambda: None)])
        self.assertEqual(results[0].status, "SURVIVED")
        self.assertFalse(results[0].ok)

    def test_a_check_that_its_mutation_breaks_is_killed(self):
        state = Box(0)
        results = falsify(
            checks={"real": lambda: state.value == 0},
            mutations=[Mutation("real", lambda: setattr(state, "value", 1))])
        self.assertEqual(results[0].status, "killed")

    def test_a_check_already_failing_needs_no_mutation(self):
        results = falsify(checks={"failing": lambda: False}, mutations=[])
        self.assertEqual(results[0].status, "killed")
        self.assertIn("currently failing", results[0].detail)

    def test_a_check_with_no_mutation_is_unproven_not_passed_over(self):
        results = falsify(checks={"untested": lambda: True}, mutations=[])
        self.assertEqual(results[0].status, "UNPROVEN")
        self.assertFalse(results[0].ok)


class TestVanillaCoreOwnFloorChecksAreFalsifiable(unittest.TestCase):
    """Turning the discipline on this package. Every check in
    vanilla_core.floor must be capable of producing a violation."""

    def test_every_floor_check_can_fail(self):
        from vanilla_core.floor import check_floor
        from vanilla_core.manifest import DISALLOWED_MARKERS, FlavorManifest

        def mk(**kw):
            base = dict(name="ok", version="1.0.0", license="MIT",
                        entrypoint="mod:run", capabilities=("a",))
            base.update(kw)
            return FlavorManifest(**base)

        self.assertEqual(check_floor(mk()), [],
                         "a clean manifest must produce no violations, or "
                         "every result below is meaningless")

        cases = {
            "name": mk(name=""),
            "version": mk(version=""),
            "license": mk(license="NotARealLicense"),
            "entrypoint": mk(entrypoint="no-colon"),
            "attribution": mk(name=f"x {sorted(DISALLOWED_MARKERS)[0]} y"),
        }
        for check, manifest in cases.items():
            with self.subTest(check=check):
                triggered = {v.check for v in check_floor(manifest)}
                self.assertIn(check, triggered,
                              f"floor check {check!r} did not fire against a "
                              "manifest built to break it — it is decorative")


if __name__ == "__main__":
    unittest.main()
