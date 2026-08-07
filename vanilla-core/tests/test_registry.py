import unittest
from pathlib import Path

from vanilla_core.registry import FloorViolationError, discover, load_flavor
from vanilla_core.manifest import FlavorManifest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class TestRegistry(unittest.TestCase):
    def test_discover_finds_example(self):
        found = discover(EXAMPLES)
        self.assertTrue(any(p.parent.name == "hello_flavor" for p in found))

    def test_load_and_run_example(self):
        manifest_path = EXAMPLES / "hello_flavor" / "flavor.toml"
        flavor = load_flavor(manifest_path)
        result = flavor.invoke(capability="greet")
        self.assertEqual(result["capability"], "greet")
        self.assertIn("hello", result["message"])

    def test_refuses_to_load_flavor_that_fails_floor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "flavor.toml"
            manifest_path.write_text(
                '[flavor]\nname = "broken"\nversion = "0.1.0"\nlicense = "not-a-real-license"\nentrypoint = "plugin:run"\n'
            )
            with self.assertRaises(FloorViolationError):
                load_flavor(manifest_path)


if __name__ == "__main__":
    unittest.main()
