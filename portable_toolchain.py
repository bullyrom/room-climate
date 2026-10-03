"""Prepares a Python interpreter built against an old glibc via uv."""

from __future__ import annotations

import subprocess
from pathlib import Path

TARGET_PYTHON_VERSION = "3.12"
UV_EXECUTABLE = "uv"
PYTHON_BINARY_RELATIVE_PATH = Path("bin") / "python"
BUILD_DEPENDENCIES = ("pyinstaller", "pyserial")


class PortableToolchain:
    """Manages a uv virtualenv whose interpreter targets glibc 2.17.

    The distribution CPython may be linked against a newer glibc, so binaries
    built with it fail on older systems. uv-managed Python builds
    (python-build-standalone) only require glibc 2.17, which makes the produced
    binary portable.
    """

    def __init__(
        self,
        directory: Path,
        python_version: str = TARGET_PYTHON_VERSION,
    ) -> None:
        """Store the toolchain directory and the target Python version."""
        self._directory = directory
        self._python_version = python_version

    @property
    def directory(self) -> Path:
        """Return the toolchain directory."""
        return self._directory

    def python(self) -> Path:
        """Return the toolchain interpreter, creating it on first use."""
        interpreter = self._directory / PYTHON_BINARY_RELATIVE_PATH
        if not interpreter.exists():
            self._create()
        return interpreter

    def _create(self) -> None:
        """Install the managed interpreter, virtualenv and build deps."""
        self._run_uv("python", "install", self._python_version)
        self._run_uv(
            "venv",
            "--python",
            self._python_version,
            "--managed-python",
            str(self._directory),
        )
        self._run_uv(
            "pip",
            "install",
            "--python",
            str(self._directory / PYTHON_BINARY_RELATIVE_PATH),
            *BUILD_DEPENDENCIES,
        )

    @staticmethod
    def _run_uv(*arguments: str) -> None:
        """Run a uv subcommand, raising on failure."""
        subprocess.run([UV_EXECUTABLE, *arguments], check=True)
