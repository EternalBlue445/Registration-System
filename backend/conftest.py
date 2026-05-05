"""Pytest configuration — makes the backend package importable from the tests directory."""
import sys
from pathlib import Path

# Add project root to sys.path so `import backend.main` works
sys.path.insert(0, str(Path(__file__).parent))
