"""Build the side-view water overlay + total lost volume from the segments layer.

Pure: takes a route, the pipes, and ``{pipe_code: [segment dict]}`` and returns a
water polyline ``[(dist, water_level)]`` along the route plus the summed
``lost_volume``. Segment distances are measured from the pipe's manhole1, so they
are mirrored when the route traverses the pipe backwards.
"""


def route_berging(route, pipes, segments_by_pipe):
    """Return ``(water_points, total_volume)`` for ``route``.

    ``water_points`` is ``[(cumulative_dist, water_level)]`` (two points per
    segment that has a water level). ``total_volume`` sums every segment's
    ``lost_volume`` over the route's pipes.
    """
    water = []
    total_volume = 0.0
    cumulative = 0.0
    for pipe_code, from_node in zip(route.pipe_codes, route.manholes):
        pipe = pipes.get(pipe_code)
        if pipe is None:
            continue
        length = pipe.length or 0.0
        forward = pipe.manhole1 == from_node
        for seg in segments_by_pipe.get(pipe_code, []):
            total_volume += seg.get("lost_volume") or 0.0
            level = seg.get("water_level")
            if level is None:
                continue
            d0, d1 = seg["dist_from"], seg["dist_to"]
            a = d0 if forward else (length - d1)
            b = d1 if forward else (length - d0)
            water.append((cumulative + a, level))
            water.append((cumulative + b, level))
        cumulative += length
    water.sort(key=lambda p: p[0])
    return water, total_volume
