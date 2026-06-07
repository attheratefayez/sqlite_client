"""Tests for core/docker_volume.py."""

import os
import pathlib
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from core.docker_volume import (
    list_volumes,
    list_directory_tree,
    find_database_files,
    copy_from_volume,
    copy_to_volume,
    cleanup_local,
    DockerError,
    DockerVolumeInfo,
    TEMP_ROOT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_docker():
    """Patch subprocess.run to return controlled output."""
    with patch("core.docker_volume.subprocess.run") as mock:
        mock.return_value = MagicMock(
            stdout="",
            stderr="",
            returncode=0,
        )
        yield mock


def _make_result(stdout: str = "", stderr: str = "") -> MagicMock:
    return MagicMock(
        stdout=stdout,
        stderr=stderr,
        returncode=0,
        check=True,
    )


# ---------------------------------------------------------------------------
# Tests: list_volumes
# ---------------------------------------------------------------------------

class TestListVolumes:
    def test_returns_volume_names(self, mock_docker):
        mock_docker.return_value = _make_result("vol1\nvol2\nvol3\n")
        assert list_volumes() == ["vol1", "vol2", "vol3"]

    def test_empty_when_no_volumes(self, mock_docker):
        mock_docker.return_value = _make_result("")
        assert list_volumes() == []

    def test_strips_whitespace(self, mock_docker):
        mock_docker.return_value = _make_result("  vol1  \n  vol2  \n")
        assert list_volumes() == ["vol1", "vol2"]

    def test_docker_not_found(self):
        with patch("core.docker_volume.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(DockerError, match="Docker not found"):
                list_volumes()

    def test_docker_error(self, mock_docker):
        mock_docker.side_effect = subprocess.CalledProcessError(
            1, ["docker"], stderr="error msg"
        )
        with pytest.raises(DockerError, match="error msg"):
            list_volumes()


# ---------------------------------------------------------------------------
# Tests: list_directory_tree / _build_tree
# ---------------------------------------------------------------------------

class TestListDirectoryTree:
    def test_root_only(self, mock_docker):
        mock_docker.return_value = _make_result("/vol\n")
        entries = list_directory_tree("test-vol")
        assert entries == [(0, "", True)]

    def test_single_db_file(self, mock_docker):
        mock_docker.return_value = _make_result("/vol\n/vol/data.db\n")
        entries = list_directory_tree("test-vol")
        assert (1, "data.db", False) in entries
        assert (0, "", True) in entries

    def test_nested_structure(self, mock_docker):
        mock_docker.return_value = _make_result(
            "/vol\n/vol/dir1\n/vol/dir1/data.db\n/vol/dir2\n/vol/dir2/sub\n/vol/dir2/sub/deep.db\n"
        )
        entries = list_directory_tree("test-vol")
        dir_entries = {p for d, p, is_dir in entries if is_dir and d > 0}
        file_entries = {p for d, p, is_dir in entries if not is_dir}
        assert "dir1" in dir_entries
        assert "dir2" in dir_entries
        assert "dir2/sub" in dir_entries
        assert "dir1/data.db" in file_entries
        assert "dir2/sub/deep.db" in file_entries

    def test_filters_non_db_files(self, mock_docker):
        mock_docker.return_value = _make_result(
            "/vol\n/vol/data.db\n/vol/readme.txt\n/vol/image.png\n"
        )
        entries = list_directory_tree("test-vol")
        files = [p for d, p, is_dir in entries if not is_dir]
        assert "data.db" in files
        assert "readme.txt" not in files
        assert "image.png" not in files

    def test_sqlite_extensions(self, mock_docker):
        mock_docker.return_value = _make_result(
            "/vol\n/vol/a.db\n/vol/b.sqlite\n/vol/c.sqlite3\n"
        )
        entries = list_directory_tree("test-vol")
        files = [p for d, p, is_dir in entries if not is_dir]
        assert "a.db" in files
        assert "b.sqlite" in files
        assert "c.sqlite3" in files

    def test_calls_docker_with_volume(self, mock_docker):
        mock_docker.return_value = _make_result("/vol\n")
        list_directory_tree("my-volume")
        args = mock_docker.call_args[0][0]
        assert "my-volume:/vol" in args
        assert "sh" in args
        assert "-c" in args
        cmd = args[args.index("-c") + 1]
        assert "find /vol" in cmd

    def test_handles_docker_error(self, mock_docker):
        mock_docker.side_effect = subprocess.CalledProcessError(
            1, ["docker"], stderr="timeout"
        )
        with pytest.raises(DockerError):
            list_directory_tree("test-vol")


# ---------------------------------------------------------------------------
# Tests: find_database_files
# ---------------------------------------------------------------------------

class TestFindDatabaseFiles:
    def test_returns_relative_paths(self, mock_docker):
        mock_docker.return_value = _make_result(
            "/vol/data.db\n/vol/sub/db.sqlite\n"
        )
        assert find_database_files("vol") == ["data.db", "sub/db.sqlite"]

    def test_empty_when_none(self, mock_docker):
        mock_docker.return_value = _make_result("")
        assert find_database_files("vol") == []


# ---------------------------------------------------------------------------
# Tests: copy_from_volume
# ---------------------------------------------------------------------------

class TestCopyFromVolume:
    @pytest.fixture(autouse=True)
    def _setup_vol_dir(self, tmp_path):
        """Use a temp dir as TEMP_ROOT so we can create real files."""
        vol_dir = tmp_path / "my-vol"
        vol_dir.mkdir(parents=True)
        self._vol_dir = vol_dir
        self._tmp_root = tmp_path
        with patch("core.docker_volume.TEMP_ROOT", tmp_path):
            yield

    def _touch_db(self, safe_name: str) -> pathlib.Path:
        """Create a real database file at the path copy_from_volume expects."""
        p = self._vol_dir / safe_name
        conn = __import__("sqlite3").connect(str(p))
        conn.execute("CREATE TABLE t (x)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        conn.close()
        return p

    def test_returns_local_path(self, mock_docker):
        mock_docker.return_value = _make_result()
        p = self._touch_db("data.db")
        path = copy_from_volume("my-vol", "data.db")
        assert path == str(p)
        assert os.path.isfile(path)

    def test_handles_subdirectory_remote_path(self, mock_docker):
        mock_docker.return_value = _make_result()
        self._touch_db("sub_dir_data.db")
        path = copy_from_volume("my-vol", "sub/dir/data.db")
        assert "sub_dir_data.db" in path
        assert os.path.isfile(path)

    def test_copied_file_is_writable(self, mock_docker):
        mock_docker.return_value = _make_result()
        self._touch_db("data.db")
        path = copy_from_volume("my-vol", "data.db")
        conn = __import__("sqlite3").connect(path)
        try:
            conn.execute("INSERT INTO t VALUES (99)")
            conn.commit()
            rows = conn.execute("SELECT x FROM t ORDER BY x").fetchall()
            assert rows == [(42,), (99,)]
        finally:
            conn.close()

    def test_docker_error(self, mock_docker):
        mock_docker.side_effect = subprocess.CalledProcessError(
            1, ["docker"], stderr="failed"
        )
        with pytest.raises(DockerError, match="failed"):
            copy_from_volume("my-vol", "data.db")


# ---------------------------------------------------------------------------
# Tests: copy_to_volume
# ---------------------------------------------------------------------------

class TestCopyToVolume:
    def test_calls_docker_cp(self, mock_docker):
        mock_docker.return_value = _make_result()
        copy_to_volume("my-vol", "data.db", "/tmp/sqlite_client_docker/my-vol/data.db")
        args = mock_docker.call_args[0][0]
        assert "sh" in args
        assert "-c" in args
        cmd = args[args.index("-c") + 1]
        assert "cp" in cmd
        assert "/out/my-vol/data.db" in cmd
        assert "/vol/data.db" in cmd

    def test_docker_error(self, mock_docker):
        mock_docker.side_effect = subprocess.CalledProcessError(
            1, ["docker"], stderr="permission"
        )
        with pytest.raises(DockerError, match="permission"):
            copy_to_volume("my-vol", "data.db", "/tmp/out.db")


# ---------------------------------------------------------------------------
# Tests: cleanup_local
# ---------------------------------------------------------------------------

class TestCleanupLocal:
    def test_removes_file_and_empty_dir(self, tmp_path):
        vol_dir = tmp_path / "my-vol"
        vol_dir.mkdir(parents=True)
        local = vol_dir / "test.db"
        local.write_text("dummy")
        assert local.exists()

        with patch("core.docker_volume.TEMP_ROOT", tmp_path):
            cleanup_local("my-vol", str(local))

        assert not local.exists()
        assert not vol_dir.exists()

    def test_keeps_dir_if_not_empty(self, tmp_path):
        vol_dir = tmp_path / "my-vol"
        vol_dir.mkdir(parents=True)
        (vol_dir / "test.db").write_text("dummy")
        (vol_dir / "other.db").write_text("dummy")

        with patch("core.docker_volume.TEMP_ROOT", tmp_path):
            cleanup_local("my-vol", str(vol_dir / "test.db"))

        assert (vol_dir / "other.db").exists()
        assert vol_dir.exists()

    def test_handles_missing_file(self, tmp_path):
        vol_dir = tmp_path / "my-vol"
        vol_dir.mkdir(parents=True)
        local = vol_dir / "nonexistent.db"

        with patch("core.docker_volume.TEMP_ROOT", tmp_path):
            cleanup_local("my-vol", str(local))
