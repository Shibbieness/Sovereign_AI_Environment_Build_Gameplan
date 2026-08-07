import unittest
from pathlib import Path

from vanilla_core.floor import check_floor
from vanilla_core.manifest import FlavorManifest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class TestFloor(unittest.TestCase):
    def test_example_flavor_passes(self):
        manifest = FlavorManifest.load(EXAMPLES / "hello_flavor" / "flavor.toml")
        self.assertEqual(check_floor(manifest), [])

    def test_missing_license_fails(self):
        manifest = FlavorManifest(name="x", version="0.1.0", license="", entrypoint="plugin:run")
        checks = {v.check for v in check_floor(manifest)}
        self.assertIn("license", checks)

    def test_missing_name_and_version_fail(self):
        manifest = FlavorManifest(name="", version="", license="MIT", entrypoint="plugin:run")
        checks = {v.check for v in check_floor(manifest)}
        self.assertIn("name", checks)
        self.assertIn("version", checks)

    def test_bad_entrypoint_fails(self):
        manifest = FlavorManifest(name="x", version="0.1.0", license="MIT", entrypoint="not_a_module_colon_callable")
        checks = {v.check for v in check_floor(manifest)}
        self.assertIn("entrypoint", checks)

    def test_anthropic_marker_fails(self):
        manifest = FlavorManifest(
            name="noreply@anthropic.com",
            version="0.1.0",
            license="AGPL-3.0-or-later",
            entrypoint="plugin:run",
        )
        checks = {v.check for v in check_floor(manifest)}
        self.assertIn("attribution", checks)

    def test_session_link_marker_fails(self):
        manifest = FlavorManifest(
            name="x",
            version="0.1.0",
            license="AGPL-3.0-or-later",
            entrypoint="plugin:run",
            capabilities=("see https://claude.ai/code/session_abc123",),
        )
        checks = {v.check for v in check_floor(manifest)}
        self.assertIn("attribution", checks)


if __name__ == "__main__":
    unittest.main()
