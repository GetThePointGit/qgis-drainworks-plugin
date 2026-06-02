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

# Pipe outline default.
PIPE_DEFAULT = "#ffffff"
MANHOLE_DEFAULT = "#398a39"

# Lost-capacity color ramp endpoints (dry -> fully flooded).
FLOODED_LOW = "#2c7fb8"    # blue, low loss
FLOODED_HIGH = "#c54141"   # red, high loss
