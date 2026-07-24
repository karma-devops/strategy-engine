"""
Guardrail test: receiver<->strategy decoupling (Track 1.8).

Enforces the 3-point contract established in the strategy-engine cleanup:
  - Receivers (api/, instances/, app/, testing/, backtests/, scripts/) must
    obtain strategy symbols ONLY via `strategies.registry` (or the SQLAlchemy
    DB engine via `instances.models`). They must NEVER import the old
    `engine.<...>` strategy module (removed: `engine/` was git-mv'd to
    `strategies/` in commit 72aff97) and must NEVER reference a concrete
    strategy class by name outside the `strategies/` package.

This prevents regression of the receiver-decoupling boundary.

Run:  pytest tests/test_receiver_decoupling.py
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Directories scanned as "live source" (exclude backups, venv, caches, data).
EXCLUDE_DIRS = {"backups", "venv", "__pycache__", ".git", "data", "node_modules", "design-system"}

# Receiver packages that must NOT reach into strategy internals directly.
RECEIVER_DIRS = ["api", "instances", "app", "testing", "backtests", "scripts", "core", "withdrawal", "monitoring"]

# Strategy symbols that receivers are ALLOWED to import — and ONLY from
# `strategies.registry` (or `instances.models` for the SQLAlchemy `engine`).
ALLOWED_REGISTRY_SYMBOLS = {
    "get_strategy",
    "STRATEGIES",
    "BaseStrategy",
    "detect_mintick",
    "list_strategies",
    "get_presets",
    "register_uploaded_strategy",
    "unregister_uploaded_strategy",
    "clone_strategy",
    "DEFAULT_FLEET",
    "get_default_fleet",
}

# The SQLAlchemy DB engine is imported as `engine` from instances.models —
# this is legitimate and unrelated to the removed strategy `engine` package.
DB_ENGINE_IMPORT_RE = re.compile(r"from instances\.models import.*\bengine\b")

# Old strategy-module import (must be fully gone from live source).
OLD_STRATEGY_IMPORT_RE = re.compile(r"^\s*(from|import)\s+engine\b")

# Concrete trading-strategy class names match `*Strategy` (e.g. EveEngineV13Strategy).
# Names below are NOT trading-strategy classes and are exempt from the leak check.
NON_TRADING_STRATEGY_NAMES = {"BaseStrategy", "ConvertedStrategy", "Strategy"}

STRATEGY_CLASS_RE = re.compile(r"class\s+(\w*Strategy)\s*\(")

# A receiver importing a known registry symbol from a NON-allowed module.
RECEIVER_SYMBOL_IMPORT_RE = re.compile(
    r"from\s+([\w\.]+)\s+import\s+(.+?)\n",
    re.DOTALL,
)


def _live_py_files() -> list[Path]:
    files: list[Path] = []
    for p in REPO.rglob("*.py"):
        parts = set(p.relative_to(REPO).parts)
        if parts & EXCLUDE_DIRS:
            continue
        files.append(p)
    return files


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def test_no_old_strategy_module_imports():
    """No live file imports the removed `engine` strategy package."""
    violations = []
    for p in _live_py_files():
        src = _read(p)
        for m in re.finditer(r"^\s*(from|import)\s+engine\b", src, re.MULTILINE):
            line = m.group(0).strip()
            # Allow the legitimate SQLAlchemy DB engine import.
            if DB_ENGINE_IMPORT_RE.search(line):
                continue
            violations.append(f"{p.relative_to(REPO)}: {line}")
    assert not violations, (
        "Found references to the removed `engine` strategy module:\n"
        + "\n".join(violations)
    )


def test_no_concrete_strategy_class_outside_strategies_package():
    """A concrete strategy class (e.g. EveEngineV13Strategy) must only be
    defined inside `strategies/` — never referenced by name elsewhere."""
    violations = []
    for p in _live_py_files():
        rel = p.relative_to(REPO)
        # strategies/ package itself is allowed to define/use the class.
        if rel.parts and rel.parts[0] == "strategies":
            continue
        src = _read(p)
        for m in STRATEGY_CLASS_RE.finditer(src):
            # Allow the base class definition (BaseStrategy) everywhere it is
            # legitimately imported via the registry — but flag concrete names.
            name = m.group(1)
            if name in NON_TRADING_STRATEGY_NAMES:
                continue
            violations.append(f"{rel}: class {name}")
    assert not violations, (
        "Concrete strategy class names leaked outside strategies/ package:\n"
        + "\n".join(violations)
    )


def test_receivers_import_strategy_symbols_only_via_registry():
    """Receiver files may import allowed registry symbols ONLY from the public
    `strategies` / `engines` package surface (or `instances.models` for the DB
    engine). They must never reach the removed `engine` module."""
    violations = []
    for p in _live_py_files():
        rel = p.relative_to(REPO)
        if not (rel.parts and rel.parts[0] in RECEIVER_DIRS):
            continue
        src = _read(p)
        for m in RECEIVER_SYMBOL_IMPORT_RE.finditer(src):
            mod = m.group(1)
            names = m.group(2)
            for sym in ALLOWED_REGISTRY_SYMBOLS:
                if re.search(rf"\b{sym}\b", names):
                    # Allowed sources: the public strategies/engines package
                    # surface, or the SQLAlchemy DB engine.
                    if (
                        mod.startswith("strategies.")
                        or mod.startswith("engines.")
                        or mod == "instances.models"
                    ):
                        continue
                    violations.append(f"{rel}: `from {mod} import {sym}`")
    assert not violations, (
        "Receivers import strategy symbols from a non-registry module:\n"
        + "\n".join(violations)
    )


def test_receiver_dirs_do_not_glob_import_strategy_module():
    """No `import engine` / `from engine import` / `import strategies` bare
    glob that would bypass the registry boundary in receiver code."""
    violations = []
    for p in _live_py_files():
        rel = p.relative_to(REPO)
        if not (rel.parts and rel.parts[0] in RECEIVER_DIRS):
            continue
        src = _read(p)
        for line in src.splitlines():
            s = line.strip()
            if OLD_STRATEGY_IMPORT_RE.match(s) and not DB_ENGINE_IMPORT_RE.search(s):
                violations.append(f"{rel}: {s}")
    assert not violations, (
        "Receiver files reference the removed `engine` module:\n"
        + "\n".join(violations)
    )
