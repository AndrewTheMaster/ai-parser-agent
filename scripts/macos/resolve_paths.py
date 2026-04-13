#!/usr/bin/env python3
"""
Resolve paths for run_simple.sh (dictionaries, terms list, writable work root).

Dictionaries (*.pdf):
  1) <project>/dictionaries/
  2) <project>/../dictionaries/
  3) macOS DMG: <dirname(backing.dmg)>/dictionaries/

Terms (.txt), first match wins:
  1) macOS DMG: next to backing .dmg → terms.txt, words.txt, sample_terms.txt, my_terms.txt
  2) <project>/data/sample_terms.txt
  3) <project>/../terms.txt, ../sample_terms.txt, ../words.txt
"""

from __future__ import annotations

import glob
import os
import pathlib
import plistlib
import subprocess
import sys


def _has_pdfs(folder: pathlib.Path) -> bool:
    return bool(glob.glob(str(folder / "*.pdf")))


def _dmg_file_for_path(project: pathlib.Path) -> pathlib.Path | None:
    if sys.platform != "darwin":
        return None
    try:
        raw = subprocess.check_output(["/usr/bin/hdiutil", "info", "-plist"], stderr=subprocess.DEVNULL, timeout=60)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    try:
        pl = plistlib.loads(raw)
    except Exception:
        return None
    proj = project.resolve()
    proj_s = str(proj)
    for img in pl.get("images", []) or []:
        ip = img.get("image-path") or img.get("Path") or img.get("path")
        if not ip:
            continue
        for ent in img.get("system-entities") or []:
            mp = ent.get("mount-point")
            if not mp:
                continue
            mp_norm = mp.rstrip("/")
            if proj_s == mp_norm or proj_s.startswith(mp_norm + os.sep):
                try:
                    return pathlib.Path(ip).expanduser().resolve()
                except OSError:
                    return pathlib.Path(ip)
    return None


def resolve_dictionary(project: pathlib.Path) -> pathlib.Path | None:
    project = project.resolve()
    candidates = [
        project / "dictionaries",
        project.parent / "dictionaries",
    ]
    for c in candidates:
        if c.is_dir() and _has_pdfs(c):
            return c
    dmg = _dmg_file_for_path(project)
    if dmg is not None:
        sibling = dmg.parent / "dictionaries"
        if sibling.is_dir() and _has_pdfs(sibling):
            return sibling
    return None


def resolve_terms(project: pathlib.Path) -> pathlib.Path | None:
    project = project.resolve()
    dmg = _dmg_file_for_path(project)
    if dmg is not None:
        parent = dmg.parent
        for name in ("terms.txt", "words.txt", "sample_terms.txt", "my_terms.txt"):
            p = parent / name
            if p.is_file():
                return p
    for c in (
        project / "data" / "sample_terms.txt",
        project.parent / "terms.txt",
        project.parent / "sample_terms.txt",
        project.parent / "words.txt",
    ):
        if c.is_file():
            return c
    return None


def resolve_workroot(project: pathlib.Path) -> pathlib.Path:
    """Writable root for .venv, .cache, output when project dir is read-only (e.g. DMG)."""
    project = project.resolve()
    probe = project / ".legal_agent_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return project
    except OSError:
        home = pathlib.Path.home() / "Library" / "Application Support" / "LegalTermsAgent"
        home.mkdir(parents=True, exist_ok=True)
        return home


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: resolve_paths.py dictionary|terms|workroot <project_dir>", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    project = pathlib.Path(sys.argv[2])
    if mode == "dictionary":
        d = resolve_dictionary(project)
        if d is None:
            return 1
        print(d, end="")
        return 0
    if mode == "terms":
        t = resolve_terms(project)
        if t is None:
            return 1
        print(t, end="")
        return 0
    if mode == "workroot":
        print(resolve_workroot(project), end="")
        return 0
    print(f"unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
