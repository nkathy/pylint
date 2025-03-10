"""Test that the directory structure of the functional tests is correct."""
from pathlib import Path

from pylint.testutils.functional.find_functional_tests import (
    get_functional_test_files_from_directory,
)


def test_directories() -> None:
    """Test that the directory structure of the functional tests is correct."""
    functional_dir = Path(__file__).parent / "functional"
    get_functional_test_files_from_directory(functional_dir)
