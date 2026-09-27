"""Freeze installed backend dependencies, with default and platform extras retained."""

import importlib.metadata as md
import json
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
project = tomllib.loads((root / "pyproject.toml").read_text())["project"]


def closure(requirements):
    pending = [Requirement(r) for r in requirements]
    seen = {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        extras = seen.get(name, set())
        if name in seen and requirement.extras <= extras:
            continue
        seen[name] = extras | requirement.extras
        distribution = md.distribution(name)
        for dependency in distribution.requires or []:
            parsed = Requirement(dependency)
            if parsed.marker is None or any(parsed.marker.evaluate({"extra": e}) for e in {"", *seen[name]}):
                pending.append(parsed)
    return sorted(seen)


runtime = closure(project["dependencies"])
dev = closure(project["dependencies"] + project["optional-dependencies"]["dev"])
for name, names in [("requirements.lock", runtime), ("requirements-dev.lock", dev)]:
    (root / name).write_text(
        "# Generated from tested installed distributions; regenerate with scripts/lock_dependencies.py\n"
        + "".join(f"{n}=={md.version(n)}\n" for n in names)
    )
licenses = []
for name in dev:
    d = md.distribution(name)
    license_text = (
        d.metadata.get("License-Expression")
        or d.metadata.get("License")
        or ", ".join(c for c in d.metadata.get_all("Classifier", []) if c.startswith("License ::"))
        or "See upstream license"
    )
    licenses.append(
        {
            "package": name,
            "version": d.version,
            "runtime": name in runtime,
            "license_metadata": license_text[:3000],
        }
    )
(root / "docs/dependency-license-inventory.json").write_text(json.dumps(licenses, indent=2) + "\n")
