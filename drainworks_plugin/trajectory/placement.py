"""Pure trajectory placement model (no QGIS).

Given the network, the current waypoints and the selected (active) waypoint, decide
what clicking another manhole does: select / insert a tussenpunt / append / prepend /
move. Returns ``(new_waypoints, new_active)`` or ``None`` when the click would need an
unreachable connection.
"""


def _seg_nodes(network, a, b):
    """The ordered manhole codes of the shortest path a->b, or None if none."""
    try:
        return network.shortest_path(a, b).manholes
    except ValueError:
        return None


def place_waypoint(network, waypoints, active_code, code):
    """Return ``(new_waypoints, new_active)`` for clicking ``code``, or ``None``."""
    wps = list(waypoints)
    if not wps:
        return [code], code
    if code in wps:
        return wps, code  # select only
    # On the current route (between two waypoints) -> insert a tussenpunt.
    if len(wps) >= 2:
        for i in range(len(wps) - 1):
            seg = _seg_nodes(network, wps[i], wps[i + 1])
            if seg and code in seg[1:-1]:
                wps.insert(i + 1, code)
                return wps, code
    # Off the route -> act relative to the selected waypoint (fallback: last).
    sel = active_code if active_code in wps else wps[-1]
    idx = wps.index(sel)
    if idx == len(wps) - 1:                      # last (incl. single) -> append
        return (wps + [code], code) if _seg_nodes(network, sel, code) else None
    if idx == 0:                                 # first -> prepend
        return ([code] + wps, code) if _seg_nodes(network, code, sel) else None
    prev, nxt = wps[idx - 1], wps[idx + 1]       # middle -> move
    if _seg_nodes(network, prev, code) and _seg_nodes(network, code, nxt):
        wps[idx] = code
        return wps, code
    return None
