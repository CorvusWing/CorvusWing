"""Shared by the kit's tests: run a script, read its RED rows, run its breaks side by side, make a scratch repository."""
import importlib.util
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOWIN = 0x08000000 if os.name == "nt" else 0


def script(skill, name):
    return ROOT / "skills" / skill / "scripts" / name


def load(path, module_name):
    """The script as a module, to read its BREAKS and call its functions."""
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(path, *args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, str(path), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=cwd, input=stdin, creationflags=NOWIN)


def red_rows(stdout):
    """The names of the self-test's RED rows: each row prints '  RED  <name> -- <detail>'."""
    names = []
    for line in stdout.splitlines():
        text = line.strip()
        if text.startswith("RED "):
            names.append(text[3:].strip().split(" -- ")[0].strip())
    return names


def run_breaks(path, breaks):
    """{break: completed run of --self-test --break NAME}, the runs side by side, each in its own scratch folder."""
    workers = max(2, min(8, (os.cpu_count() or 2)))
    with ThreadPoolExecutor(workers) as pool:
        return dict(zip(breaks, pool.map(lambda b: run(path, "--self-test", "--break", b), breaks)))


def git(folder, *args):
    r = subprocess.run(["git", "-C", str(folder), "-c", "user.name=test", "-c", "user.email=test@example.com",
                        "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NOWIN)
    if r.returncode:
        raise AssertionError("git %s failed: %s" % (" ".join(args), r.stderr))
    return r.stdout.strip()


def write(folder, rel, text):
    p = Path(folder) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def commit(folder, message):
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "--no-verify", "-m", message)
    return git(folder, "rev-parse", "HEAD")
