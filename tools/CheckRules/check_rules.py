#!/usr/bin/env python3
"""Checks repository code rules against a committed baseline.

Existing violations are recorded per file in baseline.json, so only new
violations (a file whose count grew, or a new file with violations) fail.

Usage:
    python tools/CheckRules/check_rules.py                   # check, exit 1 on new violations
    python tools/CheckRules/check_rules.py --warn-only       # report only, always exit 0
    python tools/CheckRules/check_rules.py --update-baseline # record the current state
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

RULES = {
    "cyrillic": {
        "description": "Cyrillic characters in source code or XAML",
        "extensions": (".cs", ".xaml"),
        "pattern": re.compile(r"[Ѐ-ӿ]"),
    },
    "lookup-parameter": {
        "description": "Parameter lookup by display name (LookupParameter); use BuiltInParameter or GUID",
        "extensions": (".cs",),
        "pattern": re.compile(r"\bLookupParameter\s*\("),
    },
    "bes-type-prefix": {
        "description": "Type name with the legacy BES_ prefix; use PascalCase without a prefix",
        "extensions": (".cs",),
        "pattern": re.compile(r"\b(?:class|interface|enum|struct|record)\s+BES_\w+"),
    },
    "cross-project-source": {
        "description": "Source file linked from another project folder; use a ProjectReference instead",
        "extensions": (".csproj",),
        "pattern": re.compile(r"<(?:Compile|Page)\s+Include=\"\.\.[\\/]"),
    },
    "layer-dependency": {
        "description": "Domain/Application layer uses Revit API or WPF; move it to Infrastructure or Presentation",
        "extensions": (".cs",),
        "path": re.compile(r"/(?:Domain|Application)/"),
        "pattern": re.compile(r"^\s*(?:global\s+)?using\s+(?:static\s+)?(?:\w+\s*=\s*)?(?:Autodesk\.Revit|System\.Windows)\b"),
    },
    # Cross-file rule: checked by scan_package_versions(), not line by line.
    "package-version": {
        "description": "NuGet package version differs from the version used by other projects under the same condition",
        "extensions": (),
        "pattern": None,
    },
}

SCANNED_ROOTS = ("source/",)
PACKAGE_SCANNED_ROOTS = ("source/", "tests/")
MAX_REPORTED_LINES = 5

ITEM_GROUP_OPEN = re.compile(r"<ItemGroup\b([^>]*)>")
PACKAGE_REFERENCE = re.compile(r"<PackageReference\s+Include=\"([^\"]+)\"([^>]*)>")
CONDITION = re.compile(r"Condition=\"([^\"]*)\"")
VERSION = re.compile(r"\bVersion=\"([^\"]+)\"")


def list_files(roots=SCANNED_ROOTS):
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", *roots],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [path for path in output.split("\0") if path]


def version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in re.split(r"[.-]", version))


def scan_package_versions():
    """Returns {path: [line numbers]} for package references whose literal version differs
    from the most common version of the same package under the same condition."""
    references = {}  # (package, condition) -> [(path, line, version)]
    for path in list_files(PACKAGE_SCANNED_ROOTS):
        if not path.endswith(".csproj") or not (ROOT / path).is_file():
            continue
        group_condition = ""
        text = (ROOT / path).read_text(encoding="utf-8-sig", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            group = ITEM_GROUP_OPEN.search(line)
            if group:
                condition = CONDITION.search(group.group(1))
                group_condition = condition.group(1) if condition else ""
            if "</ItemGroup>" in line:
                group_condition = ""
            for match in PACKAGE_REFERENCE.finditer(line):
                version = VERSION.search(match.group(2))
                if not version or "$(" in version.group(1):
                    continue  # property-driven versions are resolved per configuration
                own_condition = CONDITION.search(match.group(2))
                condition = " ".join(filter(None, [group_condition, own_condition.group(1) if own_condition else ""]))
                key = (match.group(1).lower(), " ".join(condition.split()))
                references.setdefault(key, []).append((path, line_number, version.group(1)))

    violations = {}
    for entries in references.values():
        versions = [version for _, _, version in entries]
        if len(set(versions)) < 2:
            continue
        expected = max(set(versions), key=lambda v: (versions.count(v), version_key(v)))
        for path, line_number, version in entries:
            if version != expected:
                violations.setdefault(path, []).append(line_number)
    return violations


def scan():
    """Returns {rule: {path: [line numbers]}} for every violation in tracked files."""
    results = {name: {} for name in RULES}
    for path in list_files():
        rules = [
            name for name, rule in RULES.items()
            if path.endswith(rule["extensions"]) and ("path" not in rule or rule["path"].search(path))
        ]
        if not rules:
            continue
        full_path = ROOT / path
        if not full_path.is_file():
            continue
        text = full_path.read_text(encoding="utf-8-sig", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name in rules:
                hits = len(RULES[name]["pattern"].findall(line))
                if name == "cyrillic":
                    hits = min(hits, 1)  # count lines, not characters
                results[name].setdefault(path, []).extend([line_number] * hits)
    results["package-version"] = scan_package_versions()
    return {name: {path: lines for path, lines in files.items() if lines} for name, files in results.items()}


def load_baseline():
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def write_baseline(results):
    baseline = {
        name: {path: len(lines) for path, lines in sorted(files.items())}
        for name, files in results.items()
    }
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    totals = ", ".join(f"{name}={sum(files.values())}" for name, files in baseline.items())
    print(f"Baseline updated: {totals}")


def annotate(level, path, line, message):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level} file={path},line={line}::{message}")


def check(results, warn_only):
    baseline = load_baseline()
    new_violations = 0
    improved = []

    for name, files in results.items():
        allowed_files = baseline.get(name, {})
        for path, lines in sorted(files.items()):
            allowed = allowed_files.get(path, 0)
            if len(lines) <= allowed:
                continue
            added = len(lines) - allowed
            new_violations += added
            message = f"[{name}] {RULES[name]['description']}: {len(lines)} found, baseline allows {allowed}"
            shown = ", ".join(str(line) for line in lines[:MAX_REPORTED_LINES])
            more = "" if len(lines) <= MAX_REPORTED_LINES else f" (+{len(lines) - MAX_REPORTED_LINES} more)"
            print(f"{path}: {message}; lines {shown}{more}")
            annotate("warning" if warn_only else "error", path, lines[0], message)

        for path, allowed in allowed_files.items():
            if len(files.get(path, [])) < allowed:
                improved.append(f"{name}: {path}")

    if improved:
        print(f"{len(improved)} baseline entries can be tightened; run with --update-baseline.")

    if new_violations == 0:
        print("Code rules check passed: no new violations.")
        return 0

    print(f"Code rules check found {new_violations} new violation(s).")
    return 0 if warn_only else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--update-baseline", action="store_true", help="record current violations as the baseline")
    parser.add_argument("--warn-only", action="store_true", help="report new violations without failing")
    args = parser.parse_args()

    results = scan()
    if args.update_baseline:
        write_baseline(results)
        return 0
    return check(results, args.warn_only)


if __name__ == "__main__":
    sys.exit(main())
