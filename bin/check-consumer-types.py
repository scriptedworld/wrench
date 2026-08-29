#!/usr/bin/env python3
"""Check that the Python pack is typed, and that a consumer can see that.

Two checks, because passing the first and failing the second is the state the
pack was already in once: the marker said "this package is typed" while the
public API carried no annotations at all.

    mypy --strict over python/wrench          the pack annotates itself
    mypy --strict over testdata/consumer      a consumer resolves those types

THE SECOND ONE HAS TO RUN AGAINST AN INSTALL. mypy honours `py.typed` for a
package it finds as an installed distribution and ignores it for source found on
MYPYPATH, so checking the consumer against the source tree passes whether or not
the marker exists. Measured: with `py.typed` deleted, the MYPYPATH form still
reported success and only the installed form reported

    Skipping analyzing "wrench": module is installed, but missing library stubs
    or py.typed marker

which is the error skid hit from outside. Installing also puts the packaging
config under test, since the marker reaches site-packages only if
`[tool.setuptools.package-data]` carries it.

THE VENV MUST NOT SEE SYSTEM SITE-PACKAGES. wrench is installed editable there,
and an editable install resolves to this very source tree, so mypy reads the
package as source and the marker stops mattering again. Measured: with
`--system-site-packages` the check passed with `py.typed` deleted, which is the
one thing it exists to catch.

So a wheel is built first, with the interpreter running this script, and a clean
venv installs that. Nothing reaches the network: the build backend comes from
the interpreter already in use, installing a built wheel needs no backend at
all, and wrench's own dependencies are not needed to type-check its surface.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "python"
CONSUMER = ROOT / "testdata" / "consumer"
SCRATCH = ROOT / ".ephemera"


def run(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, cwd=ROOT)


def check_the_pack() -> bool:
    """The pack annotates its own public surface."""
    done = run("mypy", "--strict", str(PACK / "wrench"))
    print(done.stdout.strip() or done.stderr.strip())
    return done.returncode == 0


def check_a_consumer(interpreter: Path) -> bool:
    """A consumer of the installed pack resolves its types."""
    done = run(
        "mypy",
        "--strict",
        "--no-incremental",
        "--python-executable",
        str(interpreter),
        str(CONSUMER),
    )
    print(done.stdout.strip() or done.stderr.strip())
    return done.returncode == 0


def main() -> int:
    if not CONSUMER.is_dir():
        print(f"{CONSUMER} is missing, so the consumer half asserts nothing")
        return 1

    SCRATCH.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(dir=SCRATCH, prefix="consumer-types-"))
    try:
        # Built from a copy, because setuptools reuses `python/build/` and a
        # stale one puts files in the wheel that the source no longer has.
        # Measured: with `py.typed` deleted, a build reusing that tree still
        # produced a wheel carrying it, so the check passed on a marker the
        # repository had stopped shipping.
        source = workspace / "source"
        shutil.copytree(
            PACK,
            source,
            ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__", ".pytest_cache", ".mypy_cache"),
        )

        built = run(
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--quiet",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(workspace),
            str(source),
        )
        wheels = sorted(workspace.glob("wrench-*.whl"))
        if built.returncode != 0 or not wheels:
            print("building the pack failed, so the consumer check would assert nothing")
            print(built.stdout.strip() or built.stderr.strip())
            return 1

        venv.create(workspace / "venv", system_site_packages=False, with_pip=True)
        interpreter = workspace / "venv" / "bin" / "python"

        installed = run(
            str(interpreter),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--no-index",
            str(wheels[0]),
        )
        if installed.returncode != 0:
            print("installing the built wheel failed, so the consumer check would assert nothing")
            print(installed.stdout.strip() or installed.stderr.strip())
            return 1

        pack_ok = check_the_pack()
        consumer_ok = check_a_consumer(interpreter)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if pack_ok and consumer_ok:
        print("the pack is annotated under --strict, and a consumer of the install resolves it")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
