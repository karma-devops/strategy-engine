"""Engine layer — saved engine DEFINITIONS (the user-facing var/param surface).

Three distinct concerns (per operator 2026-07-24):
  - strategies/  = trading LOGIC catalog (strategy classes + strategy.registry).
  - engines/     = saved ENGINE DEFINITIONS — named, user-authored/cloned param
                   templates binding a strategy_id to default vars (mode, profile,
                   timeframe, leverage, etc). This is the "engine.registry".
  - instances/   = DEPLOYED runs — an engine def + live config.yaml + process.

engines/registry.py holds the seed fleet below. Users create/clone engine defs
here via UI/API; instances reference a def by slug.
"""
