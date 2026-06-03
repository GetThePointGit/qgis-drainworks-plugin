"""Color constants ported from drainworks (packages/drainworks-api map styles)."""

# Object status colors (dark theme base.ts).
STATUS_COLORS = {
    "Geen": "#c54141",
    "Compleet": "#398a39",
    "Uitgevoerd": "#b7f31c",
    "UitgevoerdTijdelijk": "#01aeed",
    "WachtOpGoedkeuring": "#edc708",
    "WerkNietMogelijk": "#F89DE9",
    "AndereEigenaar": "#5b5a5a",
    "IsNieuw": "#775b94",
}

# Map symbology defaults (visible on a light QGIS canvas).
PIPE_DEFAULT = "#0079c1"     # blue line — white was invisible on the canvas
MANHOLE_DEFAULT = "#398a39"  # green nodes

# Lost-capacity color ramp endpoints (dry -> fully flooded).
FLOODED_LOW = "#2c7fb8"    # blue, low loss
FLOODED_HIGH = "#c54141"   # red, high loss
