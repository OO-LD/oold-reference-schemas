"""Releasing one module: the commits must reach what the schemas need, and a release that was
interrupted can be finished from its record."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bump
import publish


class Commits(unittest.TestCase):
    def test_the_level_a_commit_implies(self):
        for message, level in (("fix: a typo", "patch"), ("perf(x): faster", "patch"),
                               ("feat: more", "minor"), ("feat(api)!: new shape", "major"),
                               ("fix: a\n\nBREAKING CHANGE: gone", "major"),
                               ("chore: tidy", None), ("docs: words", None),
                               ("not conventional", None)):
            self.assertEqual(bump.commit_level(message), level, message)

    def test_the_strongest_commit_wins(self):
        self.assertEqual(bump.implied(["fix: a", "feat: b", "chore: c"]), "minor")
        self.assertIsNone(bump.implied(["chore: c"]))

    def test_below_one_a_break_and_a_feature_both_raise_the_minor(self):
        self.assertEqual(bump.predicted("0.3.2", ["feat!: x"]), "0.4.0")
        self.assertEqual(bump.predicted("0.3.2", ["feat: x"]), "0.4.0")
        self.assertEqual(bump.predicted("0.3.2", ["fix: x"]), "0.3.3")
        self.assertEqual(bump.predicted("1.2.3", ["feat!: x"]), "2.0.0")
        self.assertEqual(bump.predicted("0.3.2", ["chore: x"]), "0.3.2")


class Guard(unittest.TestCase):
    def test_commits_that_reach_the_floor_pass(self):
        self.assertEqual(bump.problems("m", "0.3.2", ["feat: x"], floor="0.4.0"), [])
        self.assertEqual(bump.problems("m", "0.3.2", ["fix: x"], floor="0.3.3"), [])
        self.assertEqual(bump.problems("m", "0.3.2", ["fix: x"], floor="0.3.2"), [])

    def test_a_fix_on_a_change_that_needs_a_new_line_is_refused_and_says_what_to_write(self):
        (problem,) = bump.problems("m", "0.3.2", ["fix: x"], floor="0.4.0")
        self.assertIn("0.3.3", problem)
        self.assertIn("0.4.0", problem)
        self.assertIn("feat", problem)

    def test_schema_changes_without_any_releasing_commit_are_refused(self):
        self.assertEqual(len(bump.problems("m", "0.3.2", ["chore: x"], floor="0.3.3")), 1)

    def test_a_release_that_goes_beyond_the_floor_is_fine(self):
        # the promotion to 1.0.0 is declared by the maintainers, not by a commit type
        self.assertEqual(bump.problems("m", "0.9.3", ["feat: x"], floor="0.10.0"), [])

    def test_without_a_release_tag_only_an_unreleased_module_is_accepted(self):
        self.assertIsNone(bump.baseline_problem(None, {"m": "0.0.0"}))
        self.assertIn("m", bump.baseline_problem(None, {"m": "0.3.0"}))
        self.assertIsNone(bump.baseline_problem("v0.3.0", {"m": "0.3.0"}))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Publishing(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.staged, self.target = Path(tmp.name) / "staged", Path(tmp.name) / "target"
        for rel, data in {"m/0.4.0/A.schema.json": b"a", "m/0.4.0/oold.lock.json": b"l",
                          "packages/m-0.4.0.zip": b"z", "m/0.4/A.schema.json": b"a",
                          "m/0.4/oold.lock.json": b"l"}.items():
            (self.staged / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.staged / rel).write_bytes(data)
        self.record = publish.prepare("m", "0.4.0", self.staged)

    def test_the_record_names_every_file_with_its_digest_and_splits_fixed_from_moving(self):
        self.assertEqual(self.record["module"], "m")
        self.assertEqual(sorted(self.record["fixed"]), ["m/0.4.0/A.schema.json",
                                                        "m/0.4.0/oold.lock.json",
                                                        "packages/m-0.4.0.zip"])
        self.assertEqual(sorted(self.record["moving"]),
                         ["m/0.4/A.schema.json", "m/0.4/oold.lock.json"])
        self.assertEqual(self.record["fixed"]["packages/m-0.4.0.zip"], sha(b"z"))

    def test_a_release_is_written_fixed_files_first_and_the_line_last(self):
        written = publish.publish(self.record, self.staged, self.target)
        self.assertEqual(len(written), 5)
        self.assertTrue(all(w.startswith(("m/0.4.0", "packages")) for w in written[:3]))
        self.assertTrue(all(w.startswith("m/0.4/") for w in written[3:]))

    def test_an_interrupted_release_is_finished_by_running_it_again(self):
        publish.publish(self.record, self.staged, self.target)
        (self.target / "m/0.4/A.schema.json").unlink()        # the line was not moved yet
        (self.target / "packages/m-0.4.0.zip").unlink()       # a file never arrived
        self.assertEqual(sorted(publish.publish(self.record, self.staged, self.target)),
                         ["m/0.4/A.schema.json", "packages/m-0.4.0.zip"])
        self.assertEqual(publish.publish(self.record, self.staged, self.target), [])

    def test_a_published_fixed_file_with_other_content_is_refused(self):
        publish.publish(self.record, self.staged, self.target)
        (self.target / "m/0.4.0/A.schema.json").write_bytes(b"different")
        with self.assertRaisesRegex(publish.PublishError, "different content"):
            publish.publish(self.record, self.staged, self.target)

    def test_the_moving_line_is_overwritten(self):
        (self.target / "m/0.4").mkdir(parents=True)
        (self.target / "m/0.4/A.schema.json").write_bytes(b"older patch")
        publish.publish(self.record, self.staged, self.target)
        self.assertEqual((self.target / "m/0.4/A.schema.json").read_bytes(), b"a")

    def test_a_file_changed_after_the_record_was_made_is_refused_before_any_write(self):
        (self.staged / "m/0.4/oold.lock.json").write_bytes(b"edited")
        with self.assertRaisesRegex(publish.PublishError, "changed since"):
            publish.publish(self.record, self.staged, self.target)
        self.assertFalse(self.target.exists())

    def test_the_record_is_plain_json(self):
        self.assertEqual(json.loads(json.dumps(self.record)), self.record)


if __name__ == "__main__":
    unittest.main()
