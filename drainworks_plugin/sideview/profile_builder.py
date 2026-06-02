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


def _diameter(pipe) -> float:
    return pipe.diameter if pipe.diameter is not None else 0.0


def build_profile(path, pipes: dict, observations_by_pipe: dict) -> Profile:
    """Build a Profile from a network Path.

    Parameters
    ----------
    path : drainworks_plugin.trajectory.network.Path
    pipes : dict[str, rgs_ribx.Pipe]
    observations_by_pipe : dict[str, list[rgs_ribx.Observation]]
        Observations keyed by pipe code; each has ``distance`` from the pipe's
        own start node.
    """
    profile = Profile()
    cumulative = 0.0

    for pipe_code, from_node in zip(path.pipe_codes, path.manholes):
        pipe = pipes[pipe_code]
        # Orient the pipe so that it starts at ``from_node``.
        if pipe.manhole1 == from_node:
            start_bob, end_bob = pipe.bob1, pipe.bob2
            forward = True
        else:
            start_bob, end_bob = pipe.bob2, pipe.bob1
            forward = False
        length = pipe.length if pipe.length is not None else 0.0
        diam = _diameter(pipe)
        span_start = cumulative
        span_end = cumulative + length

        profile.vertices.append(
            ProfileVertex(dist=span_start, bob=start_bob, obb=start_bob + diam)
        )
        profile.vertices.append(
            ProfileVertex(dist=span_end, bob=end_bob, obb=end_bob + diam)
        )
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
