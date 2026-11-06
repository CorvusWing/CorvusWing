"""Credit and counts: every SKILL.md names its creator twice, the README, license and bench name him, no commit message carries an AI
co-author line, and every count the kit states about itself is the kit's own count (tests/release_counts.py)."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import release_counts
import support

ROOT = support.ROOT
AUTHOR = "Ron Brazil"
LAST = "Part of CorvusWing, created by Ron Brazil. MIT License."


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    return m.group(1) if m else ""


class TestCredit(unittest.TestCase):
    def test_every_skill_names_its_creator_in_its_frontmatter_and_its_last_line(self):
        skills = sorted(ROOT.glob("skills/*/SKILL.md"))
        self.assertTrue(skills)
        for p in skills:
            with self.subTest(skill=p.parent.name):
                text = p.read_text(encoding="utf-8")
                self.assertRegex(frontmatter(text), r"(?m)^metadata:\n(?:  .*\n)*?  author: Ron Brazil$",
                                 "the frontmatter needs metadata: author: Ron Brazil")
                lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
                self.assertEqual(lines[-1], LAST, "the last line must be the credit, word for word")

    def test_the_check_fails_a_skill_missing_either_line(self):
        good = "---\nname: x\ndescription: y\nmetadata:\n  author: Ron Brazil\n---\n\nBody.\n\n" + LAST + "\n"
        self.assertIn("author: Ron Brazil", frontmatter(good))
        no_author = good.replace("metadata:\n  author: Ron Brazil\n", "")
        self.assertNotRegex(frontmatter(no_author), r"author: Ron Brazil")
        no_last = good.replace(LAST, "MIT License.")
        self.assertNotEqual([l for l in no_last.split("\n") if l.strip()][-1], LAST)

    def test_readme_license_notice_and_bench_name_the_creator(self):
        self.assertIn("Created by Ron Brazil", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("Copyright (c) 2026 Ron Brazil", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("created by Ron Brazil", (ROOT / "NOTICE.md").read_text(encoding="utf-8"))
        self.assertIn("<b>CorvusWing</b>, created by Ron Brazil,", (ROOT / "skills/bench/bench.html").read_text(encoding="utf-8"))

    def test_no_commit_message_carries_an_ai_co_author_line(self):
        r = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%B"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=support.NOWIN)
        if r.returncode:
            self.skipTest("not a git checkout: %s" % r.stderr.strip())
        self.assertNotRegex(r.stdout, r"(?im)^co-authored-by:")


class TestCounts(unittest.TestCase):
    def test_every_count_marker_is_the_kits_own_count(self):
        self.assertEqual(release_counts.disagreements(), [])

    def test_a_marker_that_disagrees_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills" / "a").mkdir(parents=True)
            (root / "skills" / "a" / "SKILL.md").write_text("x", encoding="utf-8")
            (root / "templates").mkdir()
            (root / "README.md").write_text("<!-- count:skills -->two<!-- /count --> skills; "
                                            "<!-- count:nothing -->3<!-- /count -->", encoding="utf-8")
            bad = release_counts.disagreements(root)
            self.assertIn(("README.md", "skills", "two", "one"), bad)
            self.assertIn(("README.md", "nothing", "3", "(no such count)"), bad)

    def test_every_skill_is_in_both_readme_tables(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        method = "\n".join(l for l in text.split("\n") if re.match(r"\| \*\*[A-Z]\*\*", l))
        box = "\n".join(l for l in text.split("\n") if l.startswith("| `skills/"))
        for p in sorted((ROOT / "skills").iterdir()):
            if (p / "SKILL.md").is_file():
                with self.subTest(skill=p.name):
                    self.assertIn("`%s`" % p.name, method, "the PROPHET method table names no step for it")
                    self.assertIn("`skills/%s/`" % p.name, box, "What is in the box has no row for it")

    def test_every_template_is_named_in_the_readme_row(self):
        names = [p.name for p in (ROOT / "templates").iterdir() if p.is_file()]
        self.assertEqual(release_counts.templates_unnamed((ROOT / "README.md").read_text(encoding="utf-8"), names), [])

    def test_a_template_missing_from_the_row_is_found(self):
        row = "| `templates/` | PLAN, STATE and AGENTS, plus the archive's index (ARCHIVE-README). |"
        names = ["PLAN.md", "STATE.md", "AGENTS.template.md", "ARCHIVE-README.md", "WORKLOG.md", "README.md"]
        # README must not be read as named inside ARCHIVE-README: a name counts only as a whole word
        self.assertEqual(release_counts.templates_unnamed(row, names), ["README.md", "WORKLOG.md"])

    def test_the_counts_are_the_folders(self):
        have = release_counts.counts()
        self.assertEqual(have["skills"], len([p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()]))
        self.assertGreater(have["scripts"], 0)


if __name__ == "__main__":
    unittest.main()
