"""
Tooltip widget for tkinter.
"""
import tkinter as tk
from tkinter import ttk


class ToolTip:
    """
    Creates a tooltip for a given widget.
    
    Usage:
        button = ttk.Button(root, text="Hover me")
        ToolTip(button, "This is a tooltip")
    """
    
    def __init__(self, widget, text: str, delay: int = 500, wraplength: int = 300):
        """
        Initialize tooltip.
        
        Args:
            widget: The widget to attach tooltip to
            text: Tooltip text
            delay: Delay in ms before showing tooltip
            wraplength: Maximum width before wrapping text
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        
        self.tooltip_window = None
        self.scheduled_id = None
        
        self.widget.bind('<Enter>', self._on_enter)
        self.widget.bind('<Leave>', self._on_leave)
        self.widget.bind('<ButtonPress>', self._on_leave)
    
    def _on_enter(self, event=None):
        """Schedule tooltip to show."""
        self._cancel_scheduled()
        self.scheduled_id = self.widget.after(self.delay, self._show_tooltip)
    
    def _on_leave(self, event=None):
        """Hide tooltip and cancel scheduled show."""
        self._cancel_scheduled()
        self._hide_tooltip()
    
    def _cancel_scheduled(self):
        """Cancel any scheduled tooltip show."""
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
    
    def _show_tooltip(self):
        """Show the tooltip window."""
        if self.tooltip_window:
            return
        
        # Get widget position
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Configure tooltip appearance
        self.tooltip_window.configure(bg='#333333')
        
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            justify=tk.LEFT,
            background='#333333',
            foreground='#ffffff',
            relief=tk.SOLID,
            borderwidth=1,
            wraplength=self.wraplength,
            padx=8,
            pady=4,
            font=('Segoe UI', 9)
        )
        label.pack()
        
        # Ensure tooltip is above other windows
        self.tooltip_window.lift()
    
    def _hide_tooltip(self):
        """Hide the tooltip window."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_text(self, text: str):
        """Update the tooltip text."""
        self.text = text
        if self.tooltip_window:
            self._hide_tooltip()
            self._show_tooltip()


def create_tooltip(widget, text: str, **kwargs) -> ToolTip:
    """
    Convenience function to create a tooltip.
    
    Args:
        widget: Widget to attach tooltip to
        text: Tooltip text
        **kwargs: Additional arguments for ToolTip
        
    Returns:
        ToolTip instance
    """
    return ToolTip(widget, text, **kwargs)
