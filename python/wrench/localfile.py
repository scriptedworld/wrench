"""Reading and writing files on the machine wrench is running on.

The IO, knowing nothing about the format. A reader is handed the path rather
than bytes, so substituting one in a test exercises the validation paths
against no filesystem at all.

Writes are atomic: the bytes go to a temporary beside the target and the
temporary is renamed into place, so a reader sees the previous contents or the
new ones and never a half-written file. Beside the target matters, because a
temporary elsewhere makes the move a copy across filesystems, which is not
atomic and defeats the point.

It creates no directories. A path whose parent is missing is an error, and
deciding that a directory should exist belongs to whoever chose the path.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Protocol

# What a written file ends up with. mkstemp makes a file only its owner can
# read, which is not what evidence meant to be handed around should carry.
FILE_MODE = 0o644


class Reader(Protocol):
    """What a load requires of its IO.

    A reader is handed the path and not an open handle or the bytes, so
    substituting one in a test replaces the whole IO boundary rather than only
    the parse. FR-2.5a.
    """

    def read(self, path: str) -> bytes:
        """The whole contents of the named file."""
        ...


class Writer(Protocol):
    """What a save requires of its IO."""

    def write(self, path: str, data: bytes) -> None:
        """Put the whole contents of the named file in place."""
        ...


class LocalFileIO:
    """The local filesystem, and the only IO that ships.

    Everything wrench serves reads and writes on the machine it runs on, and a
    test substitutes its own reader rather than needing a second one shipped to
    do it.
    """

    def read(self, path: str) -> bytes:
        """The file's bytes. The path is handed in rather than an open handle,
        which is what lets a test replace the whole IO boundary."""
        return Path(path).read_bytes()

    def write(self, path: str, data: bytes) -> None:
        """Write atomically: beside the target, then renamed into place, so a
        reader sees the previous bytes or the new ones and never a partial file.

        The temporary is chmodded before the rename because `mkstemp` creates it
        readable by its owner alone, and evidence meant to be handed around has
        to survive being handed around.
        """
        target = Path(path)
        handle, name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            temporary.chmod(FILE_MODE)
            # `Path.replace` is `os.replace`, so the rename is still atomic on
            # the same filesystem, which is what FR-6.3 rests on.
            temporary.replace(target)
        except Exception:
            # Until the rename lands the temporary is litter. Any path out of
            # here that is not the successful one takes it along.
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise


LOCAL_FILE = LocalFileIO()
