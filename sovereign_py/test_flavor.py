"""Tests for the ML Filesystem Vanilla Core flavor adapter.

Does not import vanilla_core — the adapter must stay usable on its own, so
these drive it the way any host would: run(capability, params).

Every test boots into its own temporary data dir and sandbox, so no test
touches a real install.

Run: python -m unittest test_flavor -v
"""

import tempfile
import unittest
from pathlib import Path

import vanilla_flavor
from vanilla_flavor import CAPABILITIES, KNOWN_GAPS, FlavorError, run


class FlavorTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.base = {
            "data_dir": str(root / "data"),
            "sandbox": str(root / "sandbox"),
        }
        # Each test gets a fresh bootstrap rather than inheriting another's.
        vanilla_flavor._STATE.clear()

    def tearDown(self):
        self._tmp.cleanup()
        vanilla_flavor._STATE.clear()

    def call(self, capability, **params):
        merged = dict(self.base)
        merged.update(params)
        return run(capability, merged)


class TestContract(FlavorTestCase):
    def test_declared_capabilities_all_dispatch(self):
        for cap in CAPABILITIES:
            self.assertIn(cap, vanilla_flavor._DISPATCH, f"{cap} declared but not dispatchable")

    def test_declared_capabilities_exclude_known_gaps(self):
        """The manifest must not promise what the code cannot do."""
        for gap in KNOWN_GAPS:
            self.assertNotIn(gap, CAPABILITIES, f"{gap} is a known gap but is declared")

    def test_unknown_capability_raises(self):
        with self.assertRaises(FlavorError):
            run("not-a-capability", {})

    def test_default_capability_is_status(self):
        self.assertIn("optional_subsystems", self.call(None))


class TestStatus(FlavorTestCase):
    def test_reports_both_stores_and_bridge(self):
        report = self.call("status")
        self.assertTrue(report["ok"], report.get("errors"))
        self.assertEqual(report["bridge_unresolved"], [])
        self.assertGreaterEqual(report["bridge_aliases"], 20)
        self.assertEqual(report["stores"]["enhanced"]["table_count"], 17)
        self.assertEqual(report["stores"]["hierarchy"]["table_count"], 10)
        self.assertEqual(report["table_count"], 27)

    def test_reports_optional_subsystems_without_raising(self):
        report = self.call("status")
        for name, state in report["optional_subsystems"].items():
            self.assertIn(state, ("available", "missing"), name)

    def test_bridge_resolves_legacy_flat_names(self):
        """Regression: part2_agent_system imports part1_foundation by bare
        name, which the bridge originally did not alias."""
        self.call("status")
        import sys

        self.assertIn("part1_foundation", sys.modules)
        self.assertIn("models", sys.modules)


class TestCapabilities(FlavorTestCase):
    def test_self_test_passes_end_to_end(self):
        result = self.call("self-test")
        self.assertTrue(result["ok"], result["steps"])
        self.assertEqual(result["table_count"], 27)
        self.assertEqual(result["known_gaps"], [])
        self.assertTrue(all(step["ok"] for step in result["steps"]))

    def test_training_blocks_are_seeded_and_serializable(self):
        """Regression: list_blocks returns ORM objects bound to a session it
        has already closed, so reading fields raised DetachedInstanceError."""
        result = self.call("training-blocks")
        self.assertGreater(result["count"], 0)
        for block in result["blocks"]:
            self.assertIsInstance(block["id"], int)
            self.assertIsInstance(block["name"], str)

    def test_chains_empty_on_fresh_database(self):
        result = self.call("chains")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 0)

    def test_search_returns_structured_empty_result(self):
        result = self.call("fs-search", query="nothing-matches-this")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 0)

    def test_filesystem_round_trip(self):
        """Write, read back, list, and find a file — the path that was
        blocked before the Master DB split routed it to the hierarchy store."""
        body = "master db routing works\nline two\n"
        written = self.call("fs-write", path="/rt.txt", content=body)
        self.assertTrue(written["ok"])
        self.assertIsInstance(written["file_id"], int)
        self.assertFalse(written["is_directory"])

        self.assertEqual(self.call("fs-read", path="/rt.txt")["content"], body)

        listing = self.call("fs-list", path="/")
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["entries"][0]["name"], "rt.txt")

        found = self.call("fs-search", query="routing works")
        self.assertEqual(found["count"], 1)
        self.assertEqual(found["results"][0]["path"], "/rt.txt")

    def test_listing_a_non_directory_is_reported_not_raised_raw(self):
        with self.assertRaises(FlavorError):
            self.call("fs-list", path="/not-a-real-dir")

    def test_search_requires_query(self):
        with self.assertRaises(FlavorError):
            self.call("fs-search")


class TestMasterDB(FlavorTestCase):
    """The two declarative Bases are routed to separate stores rather than
    merged, because six of their table names collide with different columns."""

    def test_stores_capability_reports_routing(self):
        result = self.call("stores")
        self.assertTrue(result["ok"])
        self.assertIn("hierarchy", result["routing"])
        self.assertIn("enhanced", result["routing"])

    def test_stores_are_separate_files(self):
        stores = self.call("stores")["stores"]
        self.assertNotEqual(stores["hierarchy"]["path"], stores["enhanced"]["path"])
        self.assertTrue(stores["hierarchy"]["exists"])
        self.assertTrue(stores["enhanced"]["exists"])

    def test_colliding_table_names_exist_in_both_stores(self):
        """Regression for why they cannot share one database: these table
        names are defined by both Bases with different columns."""
        stores = self.call("stores")["stores"]
        for name in ("users", "files", "ml_agents", "tags", "activity_logs"):
            self.assertIn(name, stores["hierarchy"]["tables"], name)
            self.assertIn(name, stores["enhanced"]["tables"], name)

    def test_hierarchy_file_model_has_tree_columns(self):
        """fs_engine/filesystem.py queries these; core.database.File lacks them."""
        written = self.call("fs-write", path="/tree.txt", content="x")
        self.assertIn("parent_id", written)
        self.assertIn("is_directory", written)

    def test_no_known_gaps_remain(self):
        self.assertEqual(KNOWN_GAPS, {})



if __name__ == "__main__":
    unittest.main()
