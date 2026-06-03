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
    pipe_spans: list = field(default_factory=list)  # (pipe_code, start_dist, end_dist)
    ideal: list = field(default_factory=list)       # (dist, bob) straight bob1->bob2 line


def _diameter(pipe) -> float:
    return pipe.diameter if pipe.diameter is not None else 0.0


def build_profile(path, pipes: dict, measurements_by_pipe=None,
                  observations_by_pipe=None) -> Profile:
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
    """
    measurements_by_pipe = measurements_by_pipe or {}
    observations_by_pipe = observations_by_pipe or {}
    profile = Profile()
    cumulative = 0.0

    for pipe_code, from_node in zip(path.pipe_codes, path.manholes):
        pipe = pipes[pipe_code]
        forward = pipe.manhole1 == from_node
        length = pipe.length if pipe.length is not None else 0.0
        diam = _diameter(pipe)
        span_start = cumulative
        span_end = cumulative + length

        measured = measurements_by_pipe.get(pipe_code)
        if measured:
            # Follow the measured invert (with water level), oriented along travel.
            ordered = sorted(measured, key=lambda m: m["dist"], reverse=not forward)
            for m in ordered:
                along = m["dist"] if forward else (length - m["dist"])
                profile.vertices.append(
                    ProfileVertex(
                        dist=span_start + along,
                        bob=m["bob"],
                        obb=m["obb"],
                        water_level=m.get("water_level"),
                    )
                )
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

        profile.pipe_spans.append((pipe_code, span_start, span_end))

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

    return profile
