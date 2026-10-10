#!/usr/bin/env python3
"""
main.py - Main Entry Point for Hanoi Lottery Statistical Analysis System.
Routes CLI commands, configures Windows UTF-8 console, and launches the interactive menu.
"""

import sys
from typing import List, Optional

# Configure UTF-8 stdout/stderr on Windows to avoid UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from cli import main as cli_main


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point function executing CLI dispatcher."""
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
