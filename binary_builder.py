"""Builds the standalone diagnostic binaries and publishes every artifact."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from portable_toolchain import PortableToolchain

REPO_ROOT = Path(__file__).resolve().parent
BUILD_TARGETS = (
    ("diagnose.py", "mh_z19_liveness"),
    ("calibrate.py", "mh_z19_calibrate"),
    ("monitor.py", "mh_z19_monitor"),
    ("provision.py", "mh_z19_provision"),
)
# Files copied verbatim from the repository root into the artifact directory,
# so a freshly built artifact set is always complete.
STATIC_ARTIFACTS = ("room-climate.sh",)
DIST_DIR = "dist"
BUILD_DIR = "build"
TOOLCHAIN_DIR_NAME = ".build-toolchain"
DEFAULT_ARTIFACT_DIR = "artifacts"
ARTIFACT_DIR_ENV = "ARTIFACT_DIR"
ARTIFACT_DIR = Path(os.environ.get(ARTIFACT_DIR_ENV, REPO_ROOT / DEFAULT_ARTIFACT_DIR))
EXECUTABLE_MODE = 0o755
PYINSTALLER_MODULE = "PyInstaller"


class BinaryBuilder:
    """Builds the diagnostic binaries and publishes them to the artifact dir.

    The binaries are built with a uv-managed Python that only needs glibc 2.17,
    so they start on systems with an older glibc. Every published artifact gets
    a fresh mtime so a timestamp-based sync (for example ``rsync --update``)
    always keeps the freshly built copy.
    """

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        artifact_dir: Path = ARTIFACT_DIR,
        toolchain: PortableToolchain | None = None,
        targets: tuple[tuple[str, str], ...] = BUILD_TARGETS,
        static_artifacts: tuple[str, ...] = STATIC_ARTIFACTS,
    ) -> None:
        """Store the repository root, artifact directory and targets."""
        self._repo_root = repo_root
        self._artifact_dir = artifact_dir
        self._targets = targets
        self._static_artifacts = static_artifacts
        self._toolchain = toolchain or PortableToolchain(repo_root / TOOLCHAIN_DIR_NAME)

    def build(self) -> list[Path]:
        """Build every target and publish all artifacts."""
        published = [
            self._build_target(entry_point, name) for entry_point, name in self._targets
        ]
        published.extend(self._publish_static(name) for name in self._static_artifacts)
        return published

    def _build_target(self, entry_point: str, name: str) -> Path:
        """Build one entry point and publish the resulting binary."""
        self._run_pyinstaller(entry_point, name)
        return self._publish(name)

    def _run_pyinstaller(self, entry_point: str, name: str) -> None:
        """Run PyInstaller through the portable toolchain."""
        subprocess.run(
            [
                str(self._toolchain.python()),
                "-m",
                PYINSTALLER_MODULE,
                entry_point,
                "--onefile",
                "--console",
                "--name",
                name,
                "--distpath",
                DIST_DIR,
                "--workpath",
                BUILD_DIR,
                "--specpath",
                str(self._repo_root),
                "--noconfirm",
            ],
            check=True,
            cwd=self._repo_root,
        )

    def _publish(self, name: str) -> Path:
        """Copy a built binary into the shared artifact directory."""
        return self._copy_artifact(self._repo_root / DIST_DIR / name, name)

    def _publish_static(self, name: str) -> Path:
        """Copy a repository file (e.g. room-climate.sh) into the artifact directory."""
        return self._copy_artifact(self._repo_root / name, name)

    def _copy_artifact(self, source: Path, name: str) -> Path:
        """Copy an artifact, refresh its mtime and mark it executable."""
        target = self._artifact_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if os.access(source, os.X_OK):
            target.chmod(EXECUTABLE_MODE)
        BinaryBuilder._refresh_mtime(target)
        return target

    @staticmethod
    def _refresh_mtime(path: Path) -> None:
        """Set the artifact mtime to now so it looks freshly built."""
        os.utime(path, None)


if __name__ == "__main__":
    BinaryBuilder().build()
