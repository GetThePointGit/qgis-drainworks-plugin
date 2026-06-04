"""Persistent side-view display settings (pure dataclass + dict (de)serialisation).

The dock loads/saves these via QgsSettings; this module stays QGIS-free so it is
testable.
"""

from dataclasses import dataclass, field

# Per-line default colour + width. Keys map to the lines drawn in the side-view.
LINE_DEFAULTS = {
    "bob": {"color": "#333333", "width": 2},        # BOB gemeten (measured invert)
    "crown": {"color": "#888888", "width": 1},      # Bovenkant buis
    "ideal": {"color": "#cc8400", "width": 1},      # BOB leiding (recht)
    "maaiveld": {"color": "#a0522d", "width": 1},   # Maaiveld
    "put": {"color": "#398a39", "width": 2},        # Put-lijn
    "water": {"color": "#2c7fb8", "width": 1},      # Waterpeil
}


def _default_lines():
    """Return a fresh copy of ``LINE_DEFAULTS`` (per-line colour + width)."""
    return {key: dict(value) for key, value in LINE_DEFAULTS.items()}


@dataclass
class SideViewSettings:
    """User-tunable side-view appearance."""

    legend_position: str = "top-left"   # top-left|top-right|bottom-left|bottom-right|below
    legend_white_bg: bool = True
    show_putcodes: bool = True
    lines: dict = field(default_factory=_default_lines)

    def line(self, key):
        """Return ``{'color', 'width'}`` for a line key (defaults if unknown)."""
        return self.lines.get(key, LINE_DEFAULTS.get(key, {"color": "#000000", "width": 1}))

    def to_dict(self):
        """Return a plain-dict representation."""
        return {
            "legend_position": self.legend_position,
            "legend_white_bg": self.legend_white_bg,
            "show_putcodes": self.show_putcodes,
            "lines": {key: dict(value) for key, value in self.lines.items()},
        }

    @classmethod
    def from_dict(cls, data):
        """Build from a dict, filling missing keys with defaults (legacy-safe)."""
        data = data or {}
        s = cls()
        if "legend_position" in data:
            s.legend_position = data["legend_position"]
        if "legend_white_bg" in data:
            s.legend_white_bg = bool(data["legend_white_bg"])
        if "show_putcodes" in data:
            s.show_putcodes = bool(data["show_putcodes"])
        stored = data.get("lines") or {}
        for key, default in LINE_DEFAULTS.items():
            merged = dict(default)
            merged.update({k: v for k, v in (stored.get(key) or {}).items() if k in default})
            s.lines[key] = merged
        return s
