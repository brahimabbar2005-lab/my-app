"""ComeMorocco AI — Morocco travel assistant."""
import sys

if sys.version_info < (3, 11):  # pragma: no cover
    raise SystemExit(
        f"ComeMorocco AI needs Python 3.11 or newer; this is {sys.version.split()[0]}.\n"
        "On macOS the built-in python3 is 3.9. Install a newer one from "
        "https://www.python.org/downloads/ and recreate the virtual environment."
    )

__version__ = "1.0.0"
