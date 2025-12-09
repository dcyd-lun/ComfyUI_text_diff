"""TextDiff node for comparing two text strings with GitHub-style highlighting."""

from typing import Any, Dict, List, Optional

from ..utils import compute_text_diff, format_diff_html


class TextDiff:
    """
    ComfyUI node that compares two text strings and displays differences
    with GitHub/GitLab-style highlighting.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_a": ("STRING", {"forceInput": True, "multiline": True}),
                "text_b": ("STRING", {"forceInput": True, "multiline": True}),
            },
            "optional": {
                "view_mode": (["side_by_side", "unified"], {"default": "side_by_side"}),
                "context_lines": (
                    "INT",
                    {"default": -1, "min": -1, "max": 50, "step": 1,
                     "tooltip": "Lines of context around changes (-1 = show all)"},
                ),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "compute_diff"
    OUTPUT_NODE = True
    CATEGORY = "utils/text"

    def compute_diff(
        self,
        text_a: str,
        text_b: str,
        view_mode: str = "side_by_side",
        context_lines: int = -1,
        unique_id: Optional[str] = None,
        extra_pnginfo: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compute the diff between two text strings and return HTML for display.

        Args:
            text_a: The first (original) text string
            text_b: The second (modified) text string
            view_mode: Display mode - 'unified' or 'side_by_side'
            context_lines: Number of context lines around changes (-1 = show all)
            unique_id: ComfyUI node unique identifier
            extra_pnginfo: ComfyUI workflow metadata

        Returns:
            Dict with 'ui' key containing:
                - diff_html_unified: List with unified view HTML
                - diff_html_side_by_side: List with side-by-side view HTML
                - view_mode: List with selected view mode
        """
        # Compute the diff
        diff_result = compute_text_diff(text_a, text_b, context_lines)

        # Generate BOTH HTML versions for instant view mode switching
        html_unified = format_diff_html(diff_result, "unified")
        html_side_by_side = format_diff_html(diff_result, "side_by_side")

        # Persist to workflow for reload (silently handle errors to avoid breaking execution)
        if unique_id is not None and extra_pnginfo is not None:
            try:
                self._persist_to_workflow(unique_id, extra_pnginfo, html_unified, html_side_by_side)
            except Exception:
                pass  # Persistence is optional - don't break execution if it fails

        return {
            "ui": {
                "diff_html_unified": [html_unified],
                "diff_html_side_by_side": [html_side_by_side],
                "view_mode": [view_mode],
            }
        }

    def _persist_to_workflow(self, unique_id, extra_pnginfo, html_unified, html_side_by_side):
        """Store both diff HTML versions in workflow metadata for persistence on reload."""
        if extra_pnginfo is None:
            return

        if isinstance(extra_pnginfo, list) and len(extra_pnginfo) > 0:
            extra_pnginfo = extra_pnginfo[0]

        if not isinstance(extra_pnginfo, dict):
            return

        workflow = extra_pnginfo.get("workflow")
        if workflow is None:
            return

        nodes = workflow.get("nodes")
        if nodes is None:
            return

        for node in nodes:
            if str(node.get("id")) == str(unique_id):
                widgets_values = node.get("widgets_values", [])
                if isinstance(widgets_values, list):
                    # Remove any existing HTML entries
                    widgets_values = [
                        v for v in widgets_values
                        if not (isinstance(v, str) and v.startswith("<!DOCTYPE"))
                    ]
                    # Append both HTML versions (unified first, then side_by_side)
                    widgets_values.append(html_unified)
                    widgets_values.append(html_side_by_side)
                    node["widgets_values"] = widgets_values
                break

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force re-execution when inputs change."""
        return float("nan")
