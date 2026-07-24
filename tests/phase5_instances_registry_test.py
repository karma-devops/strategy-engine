"""Track 5.5 hard test — instances/registry.py config catalog.

Verifies:
  - instances/registry.py imports without breaking instances/manager.py
  - per-instance config.yaml read/write works
  - clone_instance_config copies config into a new slug
Does NOT touch the live DB (file artifact only; DB clone is Track 5.13).
Run: venv/bin/python3 tests/phase5_instances_registry_test.py
"""
import sys
import os
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instances import registry as R
from instances import manager  # must import cleanly (no name clash)


def test_instance_config_catalog():
    # no live config yet (5.11 writes real ones)
    assert R.get_instance_config("engine-1") is None
    # write + readback
    p = R.save_instance_config("engine-1", {"slug": "engine-1", "token": "FARTCOIN", "strategy_id": "translation-test"})
    assert p.exists()
    cfg = R.get_instance_config("engine-1")
    assert cfg["token"] == "FARTCOIN"
    # clone
    newp = R.clone_instance_config("engine-1", "engine-1-clone")
    assert newp.exists()
    assert R.get_instance_config("engine-1-clone")["slug"] == "engine-1-clone"
    # cleanup test artifacts
    shutil.rmtree(R.INSTANCES_ROOT / "engine-1")
    shutil.rmtree(R.INSTANCES_ROOT / "engine-1-clone")
    assert not R.instance_config_path("engine-1").exists()
    # manager still usable
    assert hasattr(manager, "seed_default_fleet")
    print("PASS: phase5 instances/registry config catalog + no manager break")


if __name__ == "__main__":
    test_instance_config_catalog()
