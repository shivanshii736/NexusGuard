"""Run the whole suite:  python run_tests.py   (same as `pytest -q`)."""
import sys
import pytest

sys.exit(pytest.main(["-q"]))
