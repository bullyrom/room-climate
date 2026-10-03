"""Tests for the portable build toolchain."""

from __future__ import annotations

from pathlib import Path

from portable_toolchain import PortableToolchain


def interpreter(tmp_path: Path) -> Path:
    """Create a fake toolchain interpreter and return its path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.write_text("")
    return python


def test_python_returns_existing_interpreter(tmp_path: Path) -> None:
    python = interpreter(tmp_path)
    assert PortableToolchain(tmp_path).python() == python


def test_directory_is_exposed(tmp_path: Path) -> None:
    assert PortableToolchain(tmp_path).directory == tmp_path
