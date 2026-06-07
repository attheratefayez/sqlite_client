"""Docker volume operations for browsing and accessing SQLite databases.

Provides functions to list Docker volumes, browse their directory trees
for SQLite database files, and copy databases in/out of volumes via
temporary Alpine containers.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


TEMP_ROOT = pathlib.Path(tempfile.gettempdir()) / "sqlite_client_docker"
_DB_EXTENSIONS = (".db", ".sqlite", ".sqlite3")


@dataclass
class DockerVolumeInfo:
    volume_name: str
    remote_path: str
    local_path: str


class DockerError(RuntimeError):
    """Raised when a Docker CLI operation fails."""


# ---------------------------------------------------------------------------
# Docker CLI runner
# ---------------------------------------------------------------------------

def _docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ("docker", *args),
            capture_output=True, text=True, check=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise DockerError("Docker not found. Is Docker installed?")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() or e.stdout.strip() or str(e)
        raise DockerError(msg)
    except subprocess.TimeoutExpired:
        raise DockerError("Docker command timed out")


# ---------------------------------------------------------------------------
# Volume listing
# ---------------------------------------------------------------------------

def list_volumes() -> list[str]:
    """Return names of all Docker volumes on the system."""
    result = _docker("volume", "ls", "--format", "{{.Name}}")
    return [v.strip() for v in result.stdout.strip().splitlines() if v.strip()]


# ---------------------------------------------------------------------------
# Directory / file listing inside a volume
# ---------------------------------------------------------------------------

def list_directory_tree(volume: str) -> list[tuple[int, str, bool]]:
    """Return directory+DB-file listing of a volume as ``(depth, name, is_dir)`` tuples.

    The root of the volume is represented as ``(0, "", True)``.
    Subsequent entries are suitable for building a ``QTreeView`` model.
    Only ``.db`` / ``.sqlite`` / ``.sqlite3`` files are included;
    non-DB files are omitted.
    """
    ext_expr = " -o ".join(f"-name '*{e}'" for e in _DB_EXTENSIONS)
    result = _docker(
        "run", "--rm",
        "-v", f"{volume}:/vol",
        "alpine:latest",
        "sh", "-c",
        f"find /vol \\( -type d -o \\( -type f \\( {ext_expr} \\) \\) \\)",
        timeout=60,
    )
    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    return _build_tree(lines)


def _build_tree(lines: list[str]) -> list[tuple[int, str, bool]]:
    entries: list[tuple[int, str, bool]] = [(0, "", True)]
    seen_dirs: set[str] = set()

    for line in lines:
        path = line.strip()
        if path == "/vol":
            continue
        rel = path.removeprefix("/vol/")
        if not rel:
            continue
        parts = rel.split("/")
        for i in range(len(parts)):
            parent = "/".join(parts[: i + 1])
            is_dir = i < len(parts) - 1 or not any(
                rel.lower().endswith(e) for e in _DB_EXTENSIONS
            )
            if is_dir:
                if parent not in seen_dirs:
                    seen_dirs.add(parent)
                    depth = parent.count("/")
                    name = parts[i]
                    entries.append((depth + 1, parent, True))
            else:
                depth = len(parts) - 1
                entries.append((depth + 1, parent, False))
    return entries


def find_database_files(volume: str) -> list[str]:
    """Return relative paths of all database files inside *volume*."""
    ext_expr = " -o ".join(f"-name '*{e}'" for e in _DB_EXTENSIONS)
    result = _docker(
        "run", "--rm",
        "-v", f"{volume}:/vol",
        "alpine:latest",
        "sh", "-c",
        f"find /vol -type f \\( {ext_expr} \\)",
        timeout=60,
    )
    return [
        l.strip().removeprefix("/vol/")
        for l in result.stdout.strip().splitlines()
        if l.strip()
    ]


# ---------------------------------------------------------------------------
# Copy database files in/out of volumes
# ---------------------------------------------------------------------------

def temp_dir() -> pathlib.Path:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TEMP_ROOT


def copy_from_volume(volume: str, remote_path: str) -> str:
    """Copy a DB file out of *volume* to a temp location.

    Returns the local path to the copy.
    The copy is checkpointed (WAL truncated) so it is consistent.
    """
    import sqlite3

    vol_dir = TEMP_ROOT / volume
    vol_dir.mkdir(parents=True, exist_ok=True)
    safe_name = remote_path.replace("/", "_")
    local_path = str(vol_dir / safe_name)

    _docker(
        "run", "--rm",
        "-v", f"{volume}:/vol:ro",
        "-v", f"{TEMP_ROOT}:/out",
        "alpine:latest",
        "sh", "-c",
        f"cp '/vol/{remote_path}' '/out/{volume}/{safe_name}'",
        timeout=60,
    )

    tmp_path = local_path + ".tmp"
    shutil.copyfile(local_path, tmp_path)
    os.replace(tmp_path, local_path)

    conn = sqlite3.connect(local_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()

    return local_path


def copy_to_volume(volume: str, remote_path: str, local_path: str) -> None:
    """Copy a local DB file back into *volume*, overwriting the remote file."""
    safe_name = local_path.rsplit("/", 1)[-1]
    _docker(
        "run", "--rm",
        "-v", f"{volume}:/vol",
        "-v", f"{TEMP_ROOT}:/out:ro",
        "alpine:latest",
        "sh", "-c",
        f"cp '/out/{volume}/{safe_name}' '/vol/{remote_path}'",
        timeout=60,
    )


def cleanup_local(volume: str, local_path: str) -> None:
    """Remove a local DB copy and its parent directory if empty."""
    vol_dir = TEMP_ROOT / volume
    safe_name = local_path.rsplit("/", 1)[-1]
    (vol_dir / safe_name).unlink(missing_ok=True)
    if vol_dir.exists() and not any(vol_dir.iterdir()):
        vol_dir.rmdir()
