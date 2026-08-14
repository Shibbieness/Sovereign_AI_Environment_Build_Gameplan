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


def _git(repo: Path, *args: str, **env):
    e = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
         "PATH": __import__("os").environ.get("PATH", ""),
         "HOME": str(repo)}
    e.update(env)
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, env=e)


def _throwaway_repo(tmp: str) -> Path:
    repo = Path(tmp)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Clean")
    _git(repo, "config", "user.email", "clean@example.invalid")
    (repo / "f.txt").write_text("nothing interesting\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "clean commit")
    return repo


class TestHistoryScanning(unittest.TestCase):
    """The gap that let 39 hits accumulate behind a passing guard.

    leakguard scanned tracked file *contents* and nothing else. Commit
    messages and author identities are published exactly as much as files
    are, and nothing was looking at them — so the guard printed
    "no leaks — safe to publish" across a repository whose every commit
    carried a vendor address in its trailer.

    A guard that checks the payload and not the envelope is not a guard for
    anything that travels in the envelope.
    """

    def test_clean_history_passes(self):
        """Vacuity check. If --history passed everything it would also pass
        the dirty cases below for the wrong reason."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            result = run_guard("--history", cwd=repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_marker_in_a_commit_message_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            (repo / "g.txt").write_text("also nothing\n")
            _git(repo, "add", "g.txt")
            _git(repo, "commit", "-q", "-m",
                 "a change\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
            result = run_guard("--history", cwd=repo)
            self.assertEqual(result.returncode, 1, "trailer in a commit message went unreported")
            self.assertIn("noreply@anthropic.com", result.stdout)

    def test_session_link_in_a_commit_message_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            (repo / "g.txt").write_text("x\n")
            _git(repo, "add", "g.txt")
            _git(repo, "commit", "-q", "-m",
                 "a change\n\nSession: https://claude.ai/code/session_01ABC")
            self.assertEqual(run_guard("--history", cwd=repo).returncode, 1)

    def test_marker_in_the_author_identity_is_caught(self):
        """The identity is not in the message at all, so a message-only scan
        would report this repository clean."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            (repo / "g.txt").write_text("x\n")
            _git(repo, "add", "g.txt")
            _git(repo, "commit", "-q", "-m", "an entirely innocent message",
                 GIT_AUTHOR_NAME="Claude", GIT_AUTHOR_EMAIL="noreply@anthropic.com",
                 GIT_COMMITTER_NAME="Clean", GIT_COMMITTER_EMAIL="clean@example.invalid")
            result = run_guard("--history", cwd=repo)
            self.assertEqual(result.returncode, 1, "vendor address in author identity went unreported")
            self.assertIn("author", result.stdout.lower())

    def test_marker_on_an_unchecked_out_branch_is_caught(self):
        """--history must cover every ref, not just HEAD. A branch nobody has
        checked out is still published."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            _git(repo, "checkout", "-q", "-b", "side")
            (repo / "g.txt").write_text("x\n")
            _git(repo, "add", "g.txt")
            _git(repo, "commit", "-q", "-m",
                 "side work\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
            _git(repo, "checkout", "-q", "main")
            self.assertEqual(run_guard("--history", cwd=repo).returncode, 1)

    def test_file_scan_alone_misses_all_of_this(self):
        """The point, stated as a test. The default scan reports clean on a
        repository whose history is full of the very patterns it forbids —
        which is precisely what happened here for 26 commits."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _throwaway_repo(tmp)
            (repo / "g.txt").write_text("x\n")
            _git(repo, "add", "g.txt")
            _git(repo, "commit", "-q", "-m",
                 "a change\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
            self.assertEqual(run_guard(cwd=repo).returncode, 0,
                             "file scan should be clean — the files really are")
            self.assertEqual(run_guard("--history", cwd=repo).returncode, 1,
                             "history scan must catch what the file scan cannot see")


class TestThisRepository(unittest.TestCase):
    def test_repo_is_publishable(self):
        """The repo this guard lives in must itself pass. If this fails, do
        not push — read the findings first."""
        repo = HERE.parent
        result = run_guard(cwd=repo)
        self.assertEqual(result.returncode, 0, f"repo is NOT publishable:\n{result.stdout}")

    def test_repo_history_is_publishable(self):
        """Same claim, for the half nobody was checking."""
        repo = HERE.parent
        result = run_guard("--history", cwd=repo)
        self.assertEqual(result.returncode, 0, f"history is NOT publishable:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
