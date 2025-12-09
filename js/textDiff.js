/**
 * TextDiff ComfyUI Extension
 *
 * Provides a rich diff display widget for the TextDiff node using an iframe
 * to render GitHub-style HTML diffs.
 */

import { app } from "../../scripts/app.js";

// Layout constants
const NODE_HEADER_HEIGHT = 100;    // Height reserved for node header and widgets
const INITIAL_NODE_WIDTH = 300;    // Initial node width before content
const INITIAL_NODE_HEIGHT = 150;   // Initial node height before content
const MIN_CONTAINER_HEIGHT = 50;   // Minimum height for diff container
const DEFAULT_CONTAINER_HEIGHT = 200; // Default height when content exists
const MAX_AUTO_WIDTH = 600;        // Maximum width for auto-resize
const MAX_AUTO_HEIGHT = 500;       // Maximum height for auto-resize
const MIN_CONTENT_WIDTH = 300;     // Minimum content width
const MIN_CONTENT_HEIGHT = 100;    // Minimum content height

app.registerExtension({
    name: "textdiff.display",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "TextDiff") {
            return;
        }

        // Store original methods
        const onExecuted = nodeType.prototype.onExecuted;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        const onConfigure = nodeType.prototype.onConfigure;
        const onResize = nodeType.prototype.onResize;
        const onRemoved = nodeType.prototype.onRemoved;

        /**
         * Called when the node is created - sets up the diff display widget
         */
        nodeType.prototype.onNodeCreated = function() {
            if (onNodeCreated) {
                onNodeCreated.apply(this, arguments);
            }
            this.createDiffWidget();

            // Attach view_mode widget callback for instant switching
            const self = this;
            requestAnimationFrame(() => {
                const viewModeWidget = self.widgets?.find(w => w.name === "view_mode");
                if (viewModeWidget) {
                    const originalCallback = viewModeWidget.callback;
                    viewModeWidget.callback = function(newValue) {
                        if (originalCallback) {
                            originalCallback.call(self, newValue);
                        }
                        // Instant switch if we have both HTML versions
                        if (self._htmlUnified && self._htmlSideBySide) {
                            const html = newValue === "unified" ? self._htmlUnified : self._htmlSideBySide;
                            self.updateDiffDisplay(html, newValue, true); // skipResize=true
                            if (app.graph) {
                                app.graph.setDirtyCanvas(true, false);
                            }
                        }
                    };
                }
            });
        };

        /**
         * Called when the node execution completes - updates the diff display
         */
        nodeType.prototype.onExecuted = function(message) {
            if (onExecuted) {
                onExecuted.apply(this, arguments);
            }

            if (message && message.diff_html_unified && message.diff_html_side_by_side) {
                // Store both HTML versions for instant view mode switching
                this._htmlUnified = message.diff_html_unified[0];
                this._htmlSideBySide = message.diff_html_side_by_side[0];

                const viewMode = message.view_mode ? message.view_mode[0] : "side_by_side";
                const htmlContent = viewMode === "unified" ? this._htmlUnified : this._htmlSideBySide;
                this.updateDiffDisplay(htmlContent, viewMode);
            }
        };

        /**
         * Called when loading a workflow - restores the diff display
         */
        nodeType.prototype.onConfigure = function(config) {
            if (onConfigure) {
                onConfigure.apply(this, arguments);
            }

            // Find saved HTML entries in widgets_values (unified first, then side_by_side)
            const htmlEntries = [];
            if (this.widgets_values) {
                for (const val of this.widgets_values) {
                    if (typeof val === "string" && val.startsWith("<!DOCTYPE")) {
                        htmlEntries.push(val);
                    }
                }
            }

            // Restore both HTML versions if available
            if (htmlEntries.length >= 2) {
                this._htmlUnified = htmlEntries[0];
                this._htmlSideBySide = htmlEntries[1];

                // Get current view mode from widget
                const viewModeWidget = this.widgets?.find(w => w.name === "view_mode");
                const viewMode = viewModeWidget?.value || "side_by_side";
                const htmlContent = viewMode === "unified" ? this._htmlUnified : this._htmlSideBySide;

                requestAnimationFrame(() => {
                    this._hasContent = true;
                    this._userResized = true; // Preserve user's size from saved workflow
                    if (this.diffContainer) {
                        this.diffContainer.style.display = "block";
                        const availableHeight = Math.max(this.size[1] - NODE_HEADER_HEIGHT, MIN_CONTAINER_HEIGHT);
                        this.diffContainer.style.height = `${availableHeight}px`;
                    }
                    this.updateDiffDisplay(htmlContent, viewMode, true); // skipResize=true
                });
            } else if (htmlEntries.length === 1) {
                // Fallback for old saved workflows with single HTML
                const savedHtml = htmlEntries[0];
                requestAnimationFrame(() => {
                    this._hasContent = true;
                    this._userResized = true;
                    if (this.diffContainer) {
                        this.diffContainer.style.display = "block";
                        const availableHeight = Math.max(this.size[1] - NODE_HEADER_HEIGHT, MIN_CONTAINER_HEIGHT);
                        this.diffContainer.style.height = `${availableHeight}px`;
                    }
                    this.updateDiffDisplay(savedHtml, null, true);
                });
            }
        };

        /**
         * Called when user resizes the node - sync container to fill space
         */
        nodeType.prototype.onResize = function(size) {
            if (onResize) {
                onResize.apply(this, arguments);
            }

            // Sync container height to fill available space
            if (this._hasContent && this.diffContainer) {
                // Calculate available height (node height minus header/widgets)
                const availableHeight = Math.max(size[1] - NODE_HEADER_HEIGHT, MIN_CONTAINER_HEIGHT);
                this.diffContainer.style.height = `${availableHeight}px`;

                // Mark as user-resized (skip auto-resize on future runs)
                // Only set if this wasn't triggered by our own setSize
                if (!this._isAutoResizing) {
                    this._userResized = true;
                }
            }
        };

        /**
         * Called when the node is removed - cleanup to prevent memory leaks
         */
        nodeType.prototype.onRemoved = function() {
            if (onRemoved) {
                onRemoved.apply(this, arguments);
            }

            // Clean up iframe to prevent memory leaks
            if (this.diffIframe) {
                const doc = this.getIframeDocument();
                if (doc) {
                    try {
                        doc.open();
                        doc.write("");
                        doc.close();
                    } catch (e) {
                        // Ignore errors during cleanup
                    }
                }
                this.diffIframe = null;
            }
            this.diffContainer = null;
            this.diffWidget = null;
            this._htmlUnified = null;
            this._htmlSideBySide = null;
        };

        /**
         * Gets the iframe's document object for reading/writing content.
         * @returns {Document|null} The iframe document or null if unavailable
         */
        nodeType.prototype.getIframeDocument = function() {
            if (!this.diffIframe) return null;
            try {
                return this.diffIframe.contentDocument ||
                       this.diffIframe.contentWindow?.document || null;
            } catch (e) {
                return null;
            }
        };

        /**
         * Creates the iframe widget for displaying diffs
         */
        nodeType.prototype.createDiffWidget = function() {
            // Create container div - starts hidden until content arrives
            const container = document.createElement("div");
            container.style.cssText = `
                width: 100%;
                height: 0;
                overflow: auto;
                background: #1e1e1e;
                border-radius: 4px;
                border: 1px solid #3c3c3c;
                display: none;
            `;

            // Create iframe for isolated HTML rendering
            const iframe = document.createElement("iframe");
            iframe.style.cssText = `
                width: 100%;
                height: 100%;
                border: none;
                background: #1e1e1e;
            `;
            // Security: no script execution allowed
            iframe.sandbox = "allow-same-origin";
            container.appendChild(iframe);

            // Store references
            this.diffIframe = iframe;
            this.diffContainer = container;
            this._hasContent = false;
            this._userResized = false;
            this._isAutoResizing = false;

            // Add as DOM widget that fills available space
            const self = this;
            const widget = this.addDOMWidget("diff_display", "custom", container, {
                hideOnZoom: false,
                getHeight: () => {
                    if (!self._hasContent) return 0;
                    // Return current container height
                    return parseInt(container.style.height) || DEFAULT_CONTAINER_HEIGHT;
                },
                getMinHeight: () => 0,
            });

            // Store widget reference
            this.diffWidget = widget;

            // Set compact initial size (will expand when content arrives)
            this.setSize([INITIAL_NODE_WIDTH, INITIAL_NODE_HEIGHT]);
        };

        /**
         * Updates the diff display with new HTML content
         */
        nodeType.prototype.updateDiffDisplay = function(htmlContent, viewMode, skipResize = false) {
            if (!this.diffIframe || !htmlContent) {
                return;
            }

            // Show the container
            const wasEmpty = !this._hasContent;
            this._hasContent = true;
            this.diffContainer.style.display = "block";

            this.writeToIframe(htmlContent);

            // Only auto-resize on first content or if user hasn't manually resized
            if (!skipResize && (wasEmpty || !this._userResized)) {
                requestAnimationFrame(() => {
                    this.resizeToContent();
                });
            } else {
                // Just sync container to current node size
                const availableHeight = Math.max(this.size[1] - NODE_HEADER_HEIGHT, MIN_CONTAINER_HEIGHT);
                this.diffContainer.style.height = `${availableHeight}px`;
            }
        };

        /**
         * Writes HTML content to the iframe
         * @param {string} htmlContent - The HTML content to write
         */
        nodeType.prototype.writeToIframe = function(htmlContent) {
            const doc = this.getIframeDocument();
            if (!doc) return;

            try {
                doc.open();
                doc.write(htmlContent);
                doc.close();
            } catch (e) {
                console.error("TextDiff: Failed to write to iframe:", e);
            }
        };

        /**
         * Resizes the node to fit content (initial auto-size)
         */
        nodeType.prototype.resizeToContent = function() {
            if (!this.diffContainer) return;

            const doc = this.getIframeDocument();
            if (!doc || !doc.body) return;

            try {
                const contentHeight = doc.body.scrollHeight || MIN_CONTENT_HEIGHT;
                const contentWidth = doc.body.scrollWidth || MIN_CONTENT_WIDTH;

                // Set initial size based on content (reasonable defaults, user can resize)
                // Cap initial auto-size, but user can resize larger
                const initialHeight = Math.min(Math.max(contentHeight + 10, MIN_CONTENT_HEIGHT), MAX_AUTO_HEIGHT);
                const initialWidth = Math.min(Math.max(contentWidth + 20, MIN_CONTENT_WIDTH), MAX_AUTO_WIDTH);

                this.diffContainer.style.height = `${initialHeight}px`;

                // Calculate node size (add padding for node chrome)
                const nodeWidth = initialWidth + 40;
                const nodeHeight = initialHeight + NODE_HEADER_HEIGHT;

                // Mark as auto-resizing so onResize doesn't think it's user action
                this._isAutoResizing = true;
                this.setSize([nodeWidth, nodeHeight]);
                this._isAutoResizing = false;

                // Mark canvas as dirty to trigger redraw
                if (app.graph) {
                    app.graph.setDirtyCanvas(true, false);
                }
            } catch (e) {
                this._isAutoResizing = false;
                console.error("TextDiff: Failed to resize:", e);
            }
        };
    },
});
