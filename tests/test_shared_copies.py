"""Each skill is installed on its own, so the four scripts each carry their own copy of a few helpers. This test keeps
those copies identical, so a fix made to one copy cannot quietly miss the others."""
import contextlib
import inspect
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path

import support

MODULES = {skill: support.load(support.script(skill, name), "cw_copy_" + skill.replace("-", "_"))
           for skill, name in (("test-freeze", "test_freeze.py"), ("two-strikes", "two_strikes.py"),
                               ("decide-first", "decide_first.py"), ("bake-off", "bake_off.py"))}
SHARED = {
    "remove_tree": ("test-freeze", "two-strikes", "decide-first", "bake-off"),
    "when": ("decide-first", "bake-off"),
    "program": ("two-strikes", "decide-first"),
}


class TestSharedCopies(unittest.TestCase):
    def test_each_shared_helper_is_the_same_in_every_script_that_carries_it(self):
        for helper, owners in SHARED.items():
            with self.subTest(helper=helper):
                sources = {owner: inspect.getsource(getattr(MODULES[owner], helper)) for owner in owners}
                first = sources[owners[0]]
                differ = [owner for owner, text in sources.items() if text != first]
                self.assertEqual(differ, [], "%s differs from the copy in %s" % (helper, owners[0]))

    def test_each_script_signs_its_words_with_its_own_name(self):
        for skill, module in MODULES.items():
            with self.subTest(skill=skill):
                self.assertEqual(module.TOOL, skill)

    def test_remove_tree_removes_read_only_files(self):
        for skill, module in MODULES.items():
            with self.subTest(skill=skill):
                folder = Path(tempfile.mkdtemp(prefix="cw_remove_"))
                target = folder / "objects" / "ab" / "cdef"  # git writes its objects read-only, like this
                target.parent.mkdir(parents=True)
                target.write_bytes(b"x")
                os.chmod(str(target), stat.S_IREAD)
                module.remove_tree(folder)
                self.assertFalse(folder.exists())

    @unittest.skipIf(os.name != "nt" and os.geteuid() == 0, "root may delete from a folder that cannot be written")
    def test_remove_tree_says_what_it_could_not_remove(self):
        module = MODULES["bake-off"]
        folder = Path(tempfile.mkdtemp(prefix="cw_remove_"))
        stuck = folder / "held.txt"
        stuck.write_bytes(b"x")
        said, held = io.StringIO(), None
        try:
            if os.name == "nt":
                held = open(str(stuck), "rb")  # Windows does not delete a file that is open
            else:
                os.chmod(str(folder), stat.S_IREAD | stat.S_IEXEC)  # nor does any system delete from a read-only folder
            with contextlib.redirect_stderr(said):
                module.remove_tree(folder)
        finally:
            if held:
                held.close()
            if os.name != "nt":
                os.chmod(str(folder), stat.S_IRWXU)
            module.remove_tree(folder)
        self.assertIn("bake-off: cleanup could not remove", said.getvalue())
        self.assertFalse(folder.exists())


if __name__ == "__main__":
    unittest.main()
