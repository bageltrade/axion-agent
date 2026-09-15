#!/usr/bin/env python3
"""Axion Agent entry point (Python port).

Usage:
  python3 axion.py run "task" -y
  python3 axion.py chat
  python3 axion.py models | agents | skills | init [dir]
  python3 axion.py worktree list|add|remove|prune
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import main

if __name__ == "__main__":
    sys.exit(main())