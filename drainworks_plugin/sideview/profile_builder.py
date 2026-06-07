"""Assemble a longitudinal profile from a network Path.

Output is two parallel things: the invert/crown polyline (vertices) and a list
of observation markers placed at cumulative distance along the route.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProfileVertex:
    """One vertex of the invert/crown polyline."""

    dist: float                 # cumulative distance along the route (m)
    bob: float                  # invert level (m NAP)
    obb: float                  # crown level (m NAP)
    water_level: Optional[float] = None


@dataclass
class ObservationMarker:
    """An observation positioned along the route."""

    dist: float
    code: str
    char1: Optional[str] = None
    remarks: Optional[str] = None


@dataclass
class Profile:
    """A complete side-view profile."""

    vertices: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    ideal: list = field(default_factory=list)       # (dist, bob) straight bob1->bob2 line
    manholes: list = field(default_factory=list)    # (dist, manhole_code) along the route
    manhole_levels: list = field(default_factory=list)  # (dist, code, bottom_bob, ground_level)


def _diameter(pipe) -> float:
    """Return the pipe diameter, or ``0.0`` when unknown."""
    return pipe.diameter if pipe.diameter is not None else 0.0


def live_pipe_spans(route, pipes: dict, committed_codes) -> list:
    """Cumulative ``(start, end)`` distance spans of preview-only pipes along ``route``.

    Parameters
    ----------
    route : drainworks_plugin.trajectory.network.Path
        The previewed route.
    pipes : dict[str, rgs_ribx.Pipe]
        Pipes keyed by code (for their lengths).
    committed_codes : set of str
        Pipe codes of the committed trajectory; pipes outside this set are "live"
        (exist only in the preview).

    Returns
    -------
    list of (float, float)
        One span per live pipe, as cumulative distances along ``route``.
    """
    spans = []
    cumulative = 0.0
    for code in route.pipe_codes:
        pipe = pipes.get(code)
        length = (pipe.length or 0.0) if pipe is not None else 0.0
        if code not in committed_codes:
            spans.append((cumulative, cumulative + length))
        cumulative += length
    return spans


def dist_in_spans(dist, spans, eps=1e-6) -> bool:
    """Whether ``dist`` falls within (or on the boundary of) any ``(start, end)`` span."""
    return any(s - eps <= dist <= e + eps for s, e in spans)


def strip_preview_water(profile, route, pipes: dict, committed_codes) -> list:
    """Null the water level on preview-only pipes' spans (in place).

    During a live trajectory preview the not-yet-committed pipes should show only the
    BOB line, never water; stripping their spans (including the junction boundary)
    also stops the committed pool from extending across into the part being chosen.

    Parameters
    ----------
    profile : Profile
        The profile to mutate.
    route : drainworks_plugin.trajectory.network.Path
        The previewed route.
    pipes : dict[str, rgs_ribx.Pipe]
        Pipes keyed by code.
    committed_codes : set of str
        Pipe codes of the committed trajectory.

    Returns
    -------
    list of (float, float)
        The live spans (so callers can clip an overlay to match).
    """
    spans = live_pipe_spans(route, pipes, committed_codes)
    if spans:
        for v in profile.vertices:
            if dist_in_spans(v.dist, spans):
                v.water_level = None
    return spans


def build_profile(path, pipes: dict, measurements_by_pipe=None,
                  observations_by_pipe=None, manholes_by_code=None) -> Profile:
    """Build a Profile from a network Path.

    Parameters
    ----------
    path : drainworks_plugin.trajectory.network.Path
    pipes : dict[str, rgs_ribx.Pipe]
    measurements_by_pipe : dict[str, list[dict]] or None
        Measured points per pipe (``dist``, ``bob``, ``obb`` and optional
        ``water_level``). When a pipe has these, the profile follows the measured
        invert (the doorzakking) and carries the water level; otherwise it uses
        the straight ``bob1`` → ``bob2`` line.
    observations_by_pipe : dict[str, list[rgs_ribx.Observation]] or None
        Observations keyed by pipe code; each has ``distance`` from the pipe's
        own start node.
    manholes_by_code : dict[str, rgs_ribx.Manhole] or None
        Manhole objects keyed by code, used to extract ground_level for each put.
    """
    measurements_by_pipe = measurements_by_pipe or {}
    observations_by_pipe = observations_by_pipe or {}
    manholes_by_code = manholes_by_code or {}
    profile = Profile()
    cumulative = 0.0

    for pipe_code, from_node in zip(path.pipe_codes, path.manholes):
        pipe = pipes[pipe_code]
        forward = pipe.manhole1 == from_node
        length = pipe.length if pipe.length is not None else 0.0
        diam = _diameter(pipe)
        span_start = cumulative
        profile.manholes.append((span_start, from_node))
        start_bob_here = pipe.bob1 if forward else pipe.bob2
        gl = getattr(manholes_by_code.get(from_node), "ground_level", None)
        if start_bob_here is not None:
            profile.manhole_levels.append((span_start, from_node, start_bob_here, gl))
        span_end = cumulative + length

        measured = measurements_by_pipe.get(pipe_code)
        if measured:
            # Follow the measured invert (with water level), oriented along travel.
            ordered = sorted(measured, key=lambda m: m["dist"], reverse=not forward)
            pts = [
                ProfileVertex(
                    dist=span_start + (m["dist"] if forward else (length - m["dist"])),
                    bob=m["bob"], obb=m["obb"], water_level=m.get("water_level"),
                )
                for m in ordered
            ]
            # Anchor the line at the pipe's own end BOBs when the inspection does not
            # cover the whole pipe, so a partial/short measurement doesn't draw a
            # straight line across the gap to the neighbouring pipe. The anchor carries
            # the adjacent measured water level, so a pool extends (flat, clipped to the
            # invert) to the pipe end instead of stopping at the last measurement.
            anchor_start = pipe.bob1 if forward else pipe.bob2
            anchor_end = pipe.bob2 if forward else pipe.bob1
            eps = 0.05  # m
            if anchor_start is not None and (not pts or pts[0].dist - span_start > eps):
                pts.insert(0, ProfileVertex(
                    dist=span_start, bob=anchor_start, obb=anchor_start + diam,
                    water_level=pts[0].water_level if pts else None))
            if anchor_end is not None and (not pts or span_end - pts[-1].dist > eps):
                pts.append(ProfileVertex(
                    dist=span_end, bob=anchor_end, obb=anchor_end + diam,
                    water_level=pts[-1].water_level if pts else None))
            profile.vertices.extend(pts)
        else:
            start_bob = pipe.bob1 if forward else pipe.bob2
            end_bob = pipe.bob2 if forward else pipe.bob1
            if start_bob is not None:
                profile.vertices.append(
                    ProfileVertex(dist=span_start, bob=start_bob, obb=start_bob + diam)
                )
            if end_bob is not None:
                profile.vertices.append(
                    ProfileVertex(dist=span_end, bob=end_bob, obb=end_bob + diam)
                )
        # Straight BOB line of the pipe (bob1 -> bob2), oriented along travel, so
        # the measured invert's fluctuation around it is visible.
        if pipe.bob1 is not None and pipe.bob2 is not None:
            ideal_start = pipe.bob1 if forward else pipe.bob2
            ideal_end = pipe.bob2 if forward else pipe.bob1
            profile.ideal.append((span_start, ideal_start))
            profile.ideal.append((span_end, ideal_end))

        for obs in observations_by_pipe.get(pipe_code, []):
            if obs.distance is None:
                continue
            along = obs.distance if forward else (length - obs.distance)
            profile.observations.append(
                ObservationMarker(
                    dist=span_start + along,
                    code=obs.code,
                    char1=obs.char1,
                    remarks=obs.remarks,
                )
            )

        cumulative = span_end

    # Final manhole at the end of the route.
    if path.manholes:
        profile.manholes.append((cumulative, path.manholes[-1]))

    if path.manholes and path.pipe_codes:
        last = path.manholes[-1]
        last_pipe = pipes[path.pipe_codes[-1]]
        forward_last = last_pipe.manhole1 == path.manholes[-2] if len(path.manholes) >= 2 else True
        last_bob = last_pipe.bob2 if forward_last else last_pipe.bob1
        gl = getattr(manholes_by_code.get(last), "ground_level", None)
        if last_bob is not None:
            profile.manhole_levels.append((cumulative, last, last_bob, gl))

    return profile
