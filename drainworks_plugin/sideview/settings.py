"""Persistent side-view display settings (pure dataclass + dict (de)serialisation).

The dock loads/saves these via QgsSettings; this module stays QGIS-free so it is
testable.
"""

from dataclasses import asdict, dataclass


@dataclass
class SideViewSettings:
    """User-tunable side-view appearance."""

    legend_position: str = "top-left"   # or "top-right"
    legend_white_bg: bool = False
    line_color: str = "#333333"
    line_width: int = 2
    show_putcodes: bool = True

    def to_dict(self):
        """Return a plain-dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """Build from a dict, filling missing keys with defaults."""
        data = data or {}
        fields = cls().to_dict()
        fields.update({k: v for k, v in data.items() if k in fields})
        return cls(**fields)
