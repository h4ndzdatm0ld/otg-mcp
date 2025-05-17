"""
Test to ensure there are no inline comments in the codebase.
All comments should be converted to logging statements.
"""

import os

import pytest


def test_no_inline_comments():
    """Test that there are no inline comments in Python files."""
    source_dirs = ["src"]
    problematic_modules = {}

    # Allowlist for specific patterns or file beginnings (first few lines)
    allowlist_patterns = ["# noqa", "# type:", "# pragma:", "#!/usr/bin/env"]

    for source_dir in source_dirs:
        base_path = os.path.join(os.path.dirname(__file__), "..", source_dir)
        for root, _, files in os.walk(base_path):
            for file in files:
                if "hatch" in file:
                    continue
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract module name from file path
                    rel_path = os.path.relpath(
                        filepath, os.path.dirname(os.path.dirname(__file__))
                    )
                    if rel_path.startswith("src/"):
                        rel_path = rel_path[4:]  # Remove 'src/' prefix
                    module_path = rel_path.replace("/", ".").replace(".py", "")

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

                        # Check if line starts with a comment
                        if stripped_line.startswith("#"):
                            comment_lines.append((i + 1, stripped_line))

                    if comment_lines:
                        # Group by module name for better organization
                        if module_path not in problematic_modules:
                            problematic_modules[module_path] = {}
                        problematic_modules[module_path][rel_path] = comment_lines

    if problematic_modules:
        error_message = (
            "Found inline comments that should be converted to logging statements:\n\n"
        )
        for module_name, files in problematic_modules.items():
            error_message += f"Module: {module_name}\n"
            error_message += "=" * (len(module_name) + 8) + "\n"

            for filepath, lines in files.items():
                error_message += f"  File: {filepath}\n"
                for line_num, line_content in lines:
                    error_message += f"    Line {line_num}: {line_content}\n"
            error_message += "\n"

        pytest.fail(error_message)
