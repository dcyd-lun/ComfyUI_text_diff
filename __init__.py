"""
ComfyUI TextDiff - A custom node for comparing text with GitHub-style highlighting.

This package provides a ComfyUI node that compares two text strings and displays
the differences with line-level and character-level highlighting, similar to
GitHub/GitLab diff views.
"""

from .nodes import TextDiff

NODE_CLASS_MAPPINGS = {
    "TextDiff": TextDiff,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextDiff": "Text Diff",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
