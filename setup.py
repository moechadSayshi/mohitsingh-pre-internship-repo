#!/usr/bin/env python3
"""Compatibility setup script for the Twenty app.

This repository is a Node/Yarn application. The actual dependency and build
configuration lives in package.json. This script provides a simple Python
entry point for environments that expect a setup.py file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys



def main() -> int:
    """Install JavaScript dependencies using the repository's Yarn setup."""
    yarn = shutil.which("yarn")
    if yarn is None:
        print("Error: Yarn is not installed or is not available on PATH.", file=sys.stderr)
        return 1

    print("Installing Twenty app dependencies with Yarn...")
    try:
        subprocess.run([yarn, "install"], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error: dependency installation failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode or 1

    print("Dependencies installed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
