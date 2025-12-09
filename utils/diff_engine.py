"""
Diff engine for computing line-level and character-level text differences.

Uses Python's built-in difflib module for robust diff computation.
Line numbers are 1-based in all outputs.
"""

import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Regex pattern to split text into words and whitespace tokens
WHITESPACE_SPLIT_PATTERN = r'(\s+)'


@dataclass
class DiffLine:
    """Represents a single line in the diff output."""

    line_num_a: Optional[int]  # Line number in text_a (None if addition)
    line_num_b: Optional[int]  # Line number in text_b (None if deletion)
    content: str
    change_type: str  # 'unchanged', 'added', 'deleted'
    char_diffs: Optional[List[Tuple[str, str]]] = None  # (change_type, text) pairs
    is_paired: bool = False  # True only for lines from replace opcode (paired with another line)


@dataclass
class DiffResult:
    """Contains the complete diff result with lines and statistics."""

    lines: List[DiffLine] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {"additions": 0, "deletions": 0, "unchanged": 0})


def compute_text_diff(
    text_a: str, text_b: str, context_lines: int = 3
) -> DiffResult:
    """
    Compute line-by-line diff with character-level highlighting for changed lines.

    Uses difflib.SequenceMatcher for line-level comparison, then applies
    character-level diff for modified (replaced) lines.

    Args:
        text_a: The original text
        text_b: The modified text
        context_lines: Number of unchanged lines to show around changes (-1 = show all)

    Returns:
        DiffResult containing all diff lines and statistics
    """
    # Handle edge cases
    if text_a == text_b:
        lines = text_a.splitlines(keepends=True)
        diff_lines = [
            DiffLine(
                line_num_a=i + 1,
                line_num_b=i + 1,
                content=line,
                change_type="unchanged",
                char_diffs=None,
            )
            for i, line in enumerate(lines)
        ]
        return DiffResult(
            lines=diff_lines,
            stats={"additions": 0, "deletions": 0, "unchanged": len(lines)},
        )

    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)

    # Handle empty inputs
    if not lines_a and not text_a:
        lines_a = []
    elif not lines_a:
        lines_a = [text_a]

    if not lines_b and not text_b:
        lines_b = []
    elif not lines_b:
        lines_b = [text_b]

    # Use SequenceMatcher for matching blocks
    # autojunk=False ensures accurate diffs (no heuristic skipping of "junk" elements)
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
    diff_lines: List[DiffLine] = []

    stats = {"additions": 0, "deletions": 0, "unchanged": 0}

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Unchanged lines
            for idx, line in enumerate(lines_a[i1:i2]):
                diff_lines.append(
                    DiffLine(
                        line_num_a=i1 + idx + 1,
                        line_num_b=j1 + idx + 1,
                        content=line,
                        change_type="unchanged",
                        char_diffs=None,
                    )
                )
                stats["unchanged"] += 1

        elif tag == "replace":
            # Modified lines - compute character-level diffs
            old_lines = lines_a[i1:i2]
            new_lines = lines_b[j1:j2]

            # Pair up old and new lines for character diff
            max_len = max(len(old_lines), len(new_lines))
            for idx in range(max_len):
                old_line = old_lines[idx] if idx < len(old_lines) else ""
                new_line = new_lines[idx] if idx < len(new_lines) else ""

                # Compute character-level diff for this pair
                char_diffs = compute_char_diff(old_line, new_line)

                if old_line:
                    diff_lines.append(
                        DiffLine(
                            line_num_a=i1 + idx + 1 if idx < len(old_lines) else None,
                            line_num_b=None,
                            content=old_line,
                            change_type="deleted",
                            char_diffs=char_diffs,
                            is_paired=True,
                        )
                    )
                    stats["deletions"] += 1

                if new_line:
                    diff_lines.append(
                        DiffLine(
                            line_num_a=None,
                            line_num_b=j1 + idx + 1 if idx < len(new_lines) else None,
                            content=new_line,
                            change_type="added",
                            char_diffs=char_diffs,
                            is_paired=True,
                        )
                    )
                    stats["additions"] += 1

        elif tag == "delete":
            # Lines only in text_a
            for idx, line in enumerate(lines_a[i1:i2]):
                diff_lines.append(
                    DiffLine(
                        line_num_a=i1 + idx + 1,
                        line_num_b=None,
                        content=line,
                        change_type="deleted",
                        char_diffs=None,
                    )
                )
                stats["deletions"] += 1

        elif tag == "insert":
            # Lines only in text_b
            for idx, line in enumerate(lines_b[j1:j2]):
                diff_lines.append(
                    DiffLine(
                        line_num_a=None,
                        line_num_b=j1 + idx + 1,
                        content=line,
                        change_type="added",
                        char_diffs=None,
                    )
                )
                stats["additions"] += 1

    # Apply context line filtering
    if context_lines >= 0:
        diff_lines = _filter_context_lines(diff_lines, context_lines)
        # Recalculate stats after filtering
        stats = {"additions": 0, "deletions": 0, "unchanged": 0}
        for line in diff_lines:
            if line.change_type == "added":
                stats["additions"] += 1
            elif line.change_type == "deleted":
                stats["deletions"] += 1
            else:
                stats["unchanged"] += 1

    return DiffResult(lines=diff_lines, stats=stats)


def _filter_context_lines(diff_lines: List[DiffLine], context_lines: int) -> List[DiffLine]:
    """
    Filter diff lines to only show changed lines and surrounding context.

    Args:
        diff_lines: Full list of diff lines
        context_lines: Number of unchanged lines to keep around changes

    Returns:
        Filtered list with only relevant lines
    """
    if not diff_lines:
        return diff_lines

    # Find indices of all changed lines
    changed_indices = {
        i for i, line in enumerate(diff_lines)
        if line.change_type != "unchanged"
    }

    if not changed_indices:
        return diff_lines  # No changes, return all

    # Include lines within context_lines distance of any change
    included = set()
    for idx in changed_indices:
        for offset in range(-context_lines, context_lines + 1):
            target = idx + offset
            if 0 <= target < len(diff_lines):
                included.add(target)

    return [line for i, line in enumerate(diff_lines) if i in included]


def compute_char_diff(old_line: str, new_line: str) -> List[Tuple[str, str]]:
    """
    Compute word-level differences between two lines.

    Tokenizes by words (preserving whitespace) and compares word-by-word
    for more readable diffs than character-by-character comparison.

    Args:
        old_line: The original line
        new_line: The modified line

    Returns:
        List of (change_type, text) tuples where change_type is one of:
        'equal', 'delete', 'insert'
    """
    if not old_line and not new_line:
        return []

    if not old_line:
        return [("insert", new_line)]

    if not new_line:
        return [("delete", old_line)]

    # Split into tokens (words and whitespace separately)
    old_tokens = re.split(WHITESPACE_SPLIT_PATTERN, old_line)
    new_tokens = re.split(WHITESPACE_SPLIT_PATTERN, new_line)

    # Filter out empty strings from split
    old_tokens = [t for t in old_tokens if t]
    new_tokens = [t for t in new_tokens if t]

    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    result: List[Tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append(("equal", "".join(old_tokens[i1:i2])))
        elif tag == "replace":
            # For replace, show both delete and insert
            result.append(("delete", "".join(old_tokens[i1:i2])))
            result.append(("insert", "".join(new_tokens[j1:j2])))
        elif tag == "delete":
            result.append(("delete", "".join(old_tokens[i1:i2])))
        elif tag == "insert":
            result.append(("insert", "".join(new_tokens[j1:j2])))

    return result
