"""
Instance registry — the filesystem/config catalog for deployed instances.

TERMINOLOGY (keep distinct from the other two registries):
  - STRATEGY  = trading logic class (strategies/{slug}/). See strategies/registry.py.
  - ENGINE    = saved user-facing engine DEFINITION (engines/registry.py).
  - INSTANCE  = a DEPLOYED engine + config + strategy script, bound together and
                run by instances/runner.py. The instance is what actually trades.

This module is the **config catalog** layer for instances. It owns per-instance
config files (Track 5.11: instances/{slug}/config.yaml) and the clone operation
(Track 5.13: clone_instance). It is deliberately SEPARATE from instances/manager.py,
which handles runtime start/stop and the DB-backed Instance rows.

The default fleet bootstrap source of truth is engines/registry.get_default_fleet()
(consumed by manager.seed_default_fleet()); this module does not duplicate it.
"""
from pathlib import Path
from typing import Optional

import yaml

# Root: instances/{slug}/config.yaml
INSTANCES_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Per-instance config.yaml (Track 5.11 — authoritative, git-tracked)
# ---------------------------------------------------------------------------
def instance_config_path(slug: str) -> Path:
    return INSTANCES_ROOT / slug / "config.yaml"


def get_instance_config(slug: str) -> Optional[dict]:
    """Read a per-instance config.yaml. Returns None if absent."""
    p = instance_config_path(slug)
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return None


def save_instance_config(slug: str, config: dict) -> Path:
    """Write (authoritative) per-instance config.yaml. Creates subdir if needed."""
    p = instance_config_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(config, sort_keys=False, default_flow_style=False))
    return p


def list_instance_configs() -> list:
    """Return slugs that have a config.yaml on disk."""
    return sorted(
        p.parent.name
        for p in INSTANCES_ROOT.glob("*/config.yaml")
        if p.parent.is_dir() and not p.parent.name.startswith("_")
    )


# ---------------------------------------------------------------------------
# Clone (Track 5.13) — copy an instance's config + subdir to a new slug.
# DB instance row creation stays in manager.py; this clones the FILE artifact.
# ---------------------------------------------------------------------------
def clone_instance_config(src_slug: str, new_slug: str) -> Path:
    """Clone an instance's config dir into a new slug. Returns new config path."""
    src = INSTANCES_ROOT / src_slug
    dst = INSTANCES_ROOT / new_slug
    if not src.is_dir():
        raise FileNotFoundError(f"source instance '{src_slug}' not found")
    if dst.exists():
        raise FileExistsError(f"target instance '{new_slug}' already exists")
    dst.mkdir(parents=True, exist_ok=True)
    cfg = get_instance_config(src_slug)
    if cfg is not None:
        cfg = dict(cfg)
        cfg["slug"] = new_slug
        save_instance_config(new_slug, cfg)
    return instance_config_path(new_slug)
