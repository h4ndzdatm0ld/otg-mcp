"""
Test to ensure there are no inline comments in the codebase.
All comments should be converted to logging statements.
"""

import os
import sys

import pytest

import logging


logger = logging.getLogger(__name__)
# Configure logging to ensure output is visible
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   stream=sys.stdout)


def test_no_inline_comments():
    """Test that there are no inline comments in Python files."""
    # Test all Python files in source directory
    source_dirs = ["src"]
    # Check all .py files, not just schema_registry.py
    target_extension = ".py"

    # Force the logger to print to stdout
    logging.basicConfig(level=logging.DEBUG, force=True,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                      stream=sys.stdout)
    logger.setLevel(logging.DEBUG)
    print("TEST STARTING - CHECKING FOR COMMENTS")
    problematic_modules = {}

    # Allowlist for specific patterns or file beginnings (first few lines)
    allowlist_patterns = ["# noqa", "# type:", "# pragma:", "#!/usr/bin/env"]

    for source_dir in source_dirs:
        # Fix the path to use the absolute path to the project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        base_path = os.path.join(project_root, source_dir)
        print(f"Project root: {project_root}")
        print(f"Searching base path: {base_path}")
        print(f"Does path exist? {os.path.exists(base_path)}")

        # Print directory structure first
        for root, dirs, files in os.walk(base_path):
            print(f"Directory: {root}")
            print(f"Files: {files}")

        print("Now searching for Python files...")
        for root, _, files in os.walk(base_path):
            print(f"Checking dir: {root}, Files: {files}")
            for file in files:
                print(f"Found file: {file} in {root}")
                # Process all Python files
                if file.endswith(target_extension):
                    print(f"PROCESSING TARGET FILE: {file}")
                    filepath = os.path.join(root, file)
                    logger.info("Examining file: %s", filepath)

                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract module name from file path
                    rel_path = os.path.relpath(
                        filepath, os.path.dirname(os.path.dirname(__file__))
                    )
                    if rel_path.startswith("src/"):
                        rel_path = rel_path[4:]  # Remove 'src/' prefix
                    module_path = rel_path.replace("/", ".").replace(".py", "")
                    logger.info("Module path: %s", module_path)
                    comment_lines = []
                    for i, line in enumerate(content.splitlines()):
                        stripped_line = line.strip()

                        # Skip empty lines
                        if not stripped_line:
                            continue

                        # Skip lines in allowlist
                        if any(
                            pattern in stripped_line for pattern in allowlist_patterns
                        ):
                            continue

                        # Skip comments at file beginning (first 5 lines)
                        if i < 5 and stripped_line.startswith("#"):
                            continue

                        # Print every line with a # character
                        if "#" in stripped_line:
                            print(f"Line {i+1}: {stripped_line}")
                            # Skip allowlisted patterns
                            if any(pattern in stripped_line for pattern in allowlist_patterns):
                                continue

                            # Skip comments at file beginning (first 5 lines)
                            if i < 5 and stripped_line.startswith("#"):
                                continue

                            # Add to problematic lines
                            logger.info("Found comment at line %d: %s", i + 1, stripped_line)
                            comment_lines.append((i + 1, stripped_line))

                    if comment_lines:
                        # Group by module name for better organization
                        if module_path not in problematic_modules:
                            problematic_modules[module_path] = {}
                        problematic_modules[module_path][rel_path] = comment_lines

    # Always print a summary
    print(f"FOUND {len(problematic_modules)} modules with issues")
    if problematic_modules:
        error_message = (
            "Found inline comments that should be converted to logging statements:\n\n"
        )
        logger.error("FOUND COMMENT ISSUES")
        for module_name, files in problematic_modules.items():
            error_message += f"Module: {module_name}\n"
            error_message += "=" * (len(module_name) + 8) + "\n"

            for filepath, lines in files.items():
                error_message += f"  File: {filepath}\n"
                for line_num, line_content in lines:
                    error_message += f"    Line {line_num}: {line_content}\n"
            error_message += "\n"

        pytest.fail(error_message)
