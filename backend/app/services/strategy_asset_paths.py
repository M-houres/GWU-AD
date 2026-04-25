from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


_THIS_FILE = Path(__file__).resolve()


def _candidate_bases() -> tuple[Path, ...]:
    bases: list[Path] = []
    env_root = str(os.getenv("APP_PROJECT_ROOT") or "").strip()
    if env_root:
        bases.append(Path(env_root).expanduser())

    for path in (_THIS_FILE.parent, *_THIS_FILE.parents):
        if path not in bases:
            bases.append(path)

    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if path not in bases:
            bases.append(path)
    return tuple(bases)


def _fallback_project_base(bases: tuple[Path, ...]) -> Path:
    for base in bases:
        if (base / "app").exists() or (base / "scripts").exists() or (base / "backend").exists():
            return base
    return bases[0] if bases else _THIS_FILE.parent


@lru_cache(maxsize=None)
def resolve_project_path(*relative_parts: str) -> Path:
    parts = tuple(str(part) for part in relative_parts if str(part))
    if not parts:
        return _THIS_FILE.parent

    env_asset_dir = str(os.getenv("STRATEGY_ASSET_DIR") or "").strip()
    if env_asset_dir and parts[:2] == ("data", "strategy_assets"):
        env_path = Path(env_asset_dir).expanduser().joinpath(*parts[2:])
        if env_path.exists():
            return env_path

    bases = _candidate_bases()
    prefixes = ((), ("backend",))
    for base in bases:
        for prefix in prefixes:
            candidate = base.joinpath(*prefix, *parts)
            if candidate.exists():
                return candidate

    fallback_base = _fallback_project_base(bases)
    return fallback_base.joinpath(*parts)


@lru_cache(maxsize=1)
def resolve_strategy_asset_dir() -> Path:
    return resolve_project_path("data", "strategy_assets")


def resolve_strategy_asset_path(filename: str) -> Path:
    return resolve_strategy_asset_dir() / str(filename or "").strip()
