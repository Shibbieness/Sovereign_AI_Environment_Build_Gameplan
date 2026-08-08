"""Tests for the publication guard.

Mostly canary tests. A guard that has only ever been observed passing is
indistinguishable from a guard that cannot fail — the ACI corpus gate spent
its whole life reporting failure and nobody noticed it could not report
success. So every check here plants known-bad input and requires a scream.

Run: python -m unittest tools.test_leakguard -v
"""

import subprocess
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "leakguard.py"


def run_guard(*args: str, cwd: Path | None = None):
    return subprocess.run(
        [sys.executable, str(GUARD), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )


class TestDetection(unittest.TestCase):
    """Each planted secret must be caught."""

    CANARIES = {
        "vendor-email": "contact: noreply@anthropic.com\n",
        "session-link": "see https://claude.ai/code/session_01ABC\n",
        "share-link": "https://claude.ai/share/822ea960-aa74\n",
        "coauthor": "Co-Authored-By: Claude <x@y>\n",
        "private-key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n",
        "aws-key": "key = AKIAIOSFODNN7EXAMPLE\n",
        "github-token": "token = ghp_abcdefghijklmnopqrstuvwxyz0123\n",
        "anthropic-key": "k = sk-ant-abcdefghijklmnopqrstuvwxyz01\n",
        "audience-world": "WORLD-003 is an audience world entry\n",
        "capability-node": "each capability node carries a cost\n",
        "owner-distribution": "the owner distribution percentage is gated\n",
        "invariant-floor": "the invariant floor holds regardless\n",
    }

    def test_every_canary_is_detected(self):
        for name, body in self.CANARIES.items():
            with self.subTest(canary=name):
                with tempfile.TemporaryDirectory() as tmp:
                    f = Path(tmp) / "candidate.txt"
                    f.write_text(body)
                    result = run_guard(str(f))
                    self.assertEqual(result.returncode, 1, f"{name} not caught:\n{result.stdout}")
                    self.assertIn("LEAK", result.stdout)
                    self.assertIn("PUBLICATION BLOCKED", result.stdout)

    def test_clean_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "clean.py"
            f.write_text("def add(a, b):\n    return a + b\n")
            result = run_guard(str(f))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("no leaks", result.stdout)

    def test_reports_file_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "x.txt"
            f.write_text("ok\nok\nthe spending policy is draft\n")
            result = run_guard(str(f))
            self.assertIn("x.txt:3", result.stdout)

    def test_binary_content_is_flagged_not_skipped(self):
        """A database is exactly where a corpus hides. Bytes must not buy a pass."""
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "blob.db"
            f.write_bytes(b"SQLite format 3\x00\x00extra: audience world data here\x00")
            result = run_guard(str(f))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("binary", result.stdout)

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "c.txt"
            f.write_text("CAPABILITY NODE\n")
            self.assertEqual(run_guard(str(f)).returncode, 1)


class TestConfiguration(unittest.TestCase):
    def test_list_prints_denylist(self):
        result = run_guard("--list")
        self.assertEqual(result.returncode, 0)
        self.assertIn("audience world", result.stdout)

    def test_custom_denylist_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            pat = Path(tmp) / "patterns.txt"
            pat.write_text("# comment ignored\nhunter2\n")
            target = Path(tmp) / "f.txt"
            target.write_text("password is hunter2\n")
            result = run_guard("--patterns", str(pat), str(target))
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_custom_denylist_replaces_defaults(self):
        """An explicit denylist means exactly that — no silent union."""
        with tempfile.TemporaryDirectory() as tmp:
            pat = Path(tmp) / "patterns.txt"
            pat.write_text("hunter2\n")
            target = Path(tmp) / "f.txt"
            target.write_text("noreply@anthropic.com\n")
            self.assertEqual(run_guard("--patterns", str(pat), str(target)).returncode, 0)

    def test_allow_skips_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "doc.md"
            f.write_text("capability node\n")
            self.assertEqual(run_guard(str(f)).returncode, 1)


class TestExemptions(unittest.TestCase):
    def test_allowlist_is_exact_paths_only(self):
        """A glob or directory exemption would silently stop guarding a whole
        subtree. Every entry must be a concrete file path."""
        from leakguard import DEFAULT_ALLOWLIST

        for entry in DEFAULT_ALLOWLIST:
            self.assertNotIn("*", entry, entry)
            self.assertFalse(entry.endswith("/"), entry)

    def test_exempt_files_exist(self):
        """A stale exemption is an exemption nobody rechecked."""
        from leakguard import DEFAULT_ALLOWLIST

        repo = HERE.parent
        for entry in DEFAULT_ALLOWLIST:
            self.assertTrue((repo / entry).is_file(), f"exemption points at nothing: {entry}")


class TestThisRepository(unittest.TestCase):
    def test_repo_is_publishable(self):
        """The repo this guard lives in must itself pass. If this fails, do
        not push — read the findings first."""
        repo = HERE.parent
        result = run_guard(cwd=repo)
        self.assertEqual(result.returncode, 0, f"repo is NOT publishable:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
