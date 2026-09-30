"""Locate editable checkout data or data bundled with an installed wheel."""

from pathlib import Path


def data_root() -> Path:
    package_dir = Path(__file__).resolve().parent
    checkout = package_dir.parent
    if (checkout / "tasks").is_dir() and (checkout / "third_party" / "unity").is_dir():
        return checkout
    return package_dir / "_data"
