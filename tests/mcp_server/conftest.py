"""conftest for mcp-server tests: makes the mcp-server/ directory importable."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-server"))
