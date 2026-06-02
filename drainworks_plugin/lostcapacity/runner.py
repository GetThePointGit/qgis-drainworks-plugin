"""Compute lost capacity from a GeoPackage and write results back to it."""

from collections import defaultdict

from osgeo import ogr

import rgs_ribx

from drainworks_plugin.io.geopackage_store import read_manholes, read_pipes


def _read_measurement_profiles(gpkg_path) -> dict:
    """Read interior measurement points per pipe into MeasurementPoint objects."""
    ds = ogr.Open(str(gpkg_path))
    layer = ds.GetLayerByName("measurements")
    profiles = defaultdict(list)
    if layer is None:
        return profiles
    for feat in layer:
        profiles[feat.GetField("pipe_code")].append(
            rgs_ribx.MeasurementPoint(
                dist=feat.GetField("dist"),
                bob=feat.GetField("bob"),
                obb=feat.GetField("obb"),
            )
        )
    return profiles


def compute_and_store(gpkg_path) -> int:
    """Run lost-capacity and update the ``measurements`` layer in place.

    Returns the number of measurement rows updated.
    """
    manholes = {m.code: m for m in read_manholes(gpkg_path)}
    pipes = {p.code: p for p in read_pipes(gpkg_path)}
    profiles = _read_measurement_profiles(gpkg_path)

    rgs_ribx.compute_lost_capacity(manholes, pipes, profiles)

    # Write results back. Match rows by (pipe_code, dist).
    results = {}
    for pipe_code, points in profiles.items():
        for mp in points:
            results[(pipe_code, round(mp.dist, 6))] = mp

    ds = ogr.Open(str(gpkg_path), update=1)
    layer = ds.GetLayerByName("measurements")
    updated = 0
    layer.ResetReading()
    for feat in layer:
        key = (feat.GetField("pipe_code"), round(feat.GetField("dist"), 6))
        mp = results.get(key)
        if mp is None:
            continue
        if mp.water_level is None:
            feat.SetFieldNull("water_level")
        else:
            feat.SetField("water_level", mp.water_level)
        if mp.flooded_pct is None:
            feat.SetFieldNull("flooded_pct")
        else:
            feat.SetField("flooded_pct", float(mp.flooded_pct))
        layer.SetFeature(feat)
        updated += 1
    ds = None
    return updated
