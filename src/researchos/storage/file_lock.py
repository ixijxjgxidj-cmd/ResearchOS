"""Cross-platform file locking mechanism for concurrent safe operations."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import portalocker

from researchos.core.exceptions import LockAcquisitionError


@contextmanager
def file_lock(lock_path: Path | str, timeout: float = 10.0) -> Generator[Path, None, None]:
    """Acquires an exclusive file lock on the target lock_path with a timeout.

    Args:
        lock_path: Path to the lock file.
        timeout: Maximum seconds to wait before raising LockAcquisitionError.
    """
    path = Path(lock_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with portalocker.Lock(
            str(path),
            mode="a+",
            timeout=timeout,
        ):
            yield path
    except portalocker.exceptions.LockException as exc:
        raise LockAcquisitionError(
            f"Failed to acquire lock on {path} within {timeout}s: {exc}"
        ) from exc
