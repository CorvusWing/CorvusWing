#!/usr/bin/env python3
"""release_counts.py -- every count the kit states about itself, counted from the kit, never typed.

A count in the README sits between two markers, as in

    The <!-- count:scripts -->six<!-- /count --> scripts need Python 3.8 or newer.

and this script writes the number there from the files themselves: the skills (each folder under skills/ holding a SKILL.md),
the templates (each file in templates/), and the scripts (each .py under skills/*/scripts/). Small numbers are written as words
at the start of a sentence and in running text; a marker may ask for digits with `count:skills:digits`.

USAGE
    python3 tests/release_counts.py            print each count, and each marker that disagrees (exit 1 if any)
    python3 tests/release_counts.py --write    write every marker from the counts (exit 0)
The kit's tests (tests/test_release_counts.py) fail when a marker disagrees, so a count cannot go stale unnoticed.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["README.md"]  # every file whose text states a count about the kit
MARKER = re.compile(r"<!-- count:([a-z]+)(:digits)? -->(.*?)<!-- /count -->")
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen",
         "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]


def counts(root=ROOT):
    """The kit's counts, from its files."""
    return {
        "skills": sum(1 for p in (root / "skills").iterdir() if (p / "SKILL.md").is_file()),
        "templates": sum(1 for p in (root / "templates").iterdir() if p.is_file()),
        "scripts": sum(1 for p in (root / "skills").glob("*/scripts/*.py")),
    }


def render(n, digits, capital):
    text = str(n) if digits or n >= len(WORDS) else WORDS[n]
    return text[:1].upper() + text[1:] if capital else text


def fill(text, have):
    """The text with every marker written from the counts, and the markers that named an unknown count."""
    unknown = []

    def one(m):
        name, digits, old = m.group(1), bool(m.group(2)), m.group(3)
        if name not in have:
            unknown.append(name)
            return m.group(0)
        capital = bool(old[:1].isupper())
        return "<!-- count:%s%s -->%s<!-- /count -->" % (name, m.group(2) or "", render(have[name], digits, capital))

    return MARKER.sub(one, text), unknown


def disagreements(root=ROOT):
    """Each marker whose text is not the count, as (file, name, written, counted)."""
    have, out = counts(root), []
    for rel in FILES:
        text = (root / rel).read_text(encoding="utf-8")
        for m in MARKER.finditer(text):
            name, digits, old = m.group(1), bool(m.group(2)), m.group(3)
            want = render(have[name], digits, bool(old[:1].isupper())) if name in have else None
            if want != old:
                out.append((rel, name, old, want if want is not None else "(no such count)"))
    return out


def main(argv):
    have = counts()
    print("the kit: " + ", ".join("%d %s" % (n, k) for k, n in have.items()))
    if "--write" in argv:
        for rel in FILES:
            p = ROOT / rel
            text = p.read_text(encoding="utf-8")
            new, unknown = fill(text, have)
            if unknown:
                print("REFUSED: %s names a count that does not exist: %s" % (rel, ", ".join(unknown)))
                return 1
            if new != text:
                with open(str(p), "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
                print("wrote %s" % rel)
        return 0
    bad = disagreements()
    for rel, name, old, want in bad:
        print("  %s: count:%s says %r, the kit has %r" % (rel, name, old, want))
    print("release counts %s -- %d marker(s) disagree" % ("RED" if bad else "GREEN", len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
