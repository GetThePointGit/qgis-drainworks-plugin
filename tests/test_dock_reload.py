"""``DrainworksDock._reload_base_data`` — verse basisdata zonder heropenen.

De dock is Qt en heeft geen interactie-harnas, maar ``_reload_base_data`` is
bewust GUI-vrij: hier draait hij op een via ``__new__`` gemaakte dock zonder
Qt-initialisatie, zodat we headless kunnen borgen dat handmatig gecorrigeerde
BOB's het zijaanzicht bereiken zonder de GeoPackage opnieuw te openen
(klantmelding Homeruskwartier).
"""

import rgs_ribx

from drainworks_plugin.io.geopackage_store import write_base
from drainworks_plugin.pipeline.enrich import enrich


def _stub(gpkg_path):
    """Return an uninitialised dock carrying only the state the reload needs."""
    from drainworks_plugin.ui.dock import DrainworksDock

    stub = DrainworksDock.__new__(DrainworksDock)
    stub.gpkg_path = str(gpkg_path)
    return stub


def _base_gpkg(fixtures_dir, tmp_gpkg):
    """Import + enrich the inclined fixture into ``tmp_gpkg``."""
    res = rgs_ribx.build_from_ribx(fixtures_dir / "inclined.ribx")
    write_base(tmp_gpkg, res.manholes, res.pipes, res.raw_measurements)
    enrich(tmp_gpkg, correct_bob=True)
    return tmp_gpkg


def test_reload_base_data_picks_up_edited_bob(fixtures_dir, tmp_gpkg):
    from drainworks_plugin.ui.dock import DrainworksDock

    _base_gpkg(fixtures_dir, tmp_gpkg)
    stub = _stub(tmp_gpkg)
    DrainworksDock._reload_base_data(stub)
    code, before = next(iter(stub.pipes_by_code.items()))
    assert stub.network is not None
    assert stub._manholes_by_code
    assert stub.measurements_by_pipe
    assert stub._segments_by_pipe

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg), update=1)
    layer = ds.GetLayerByName("pipes")
    feat = layer.GetNextFeature()
    feat.SetField("bob2", feat.GetField("bob2") - 1.0)
    layer.SetFeature(feat)
    ds = None

    DrainworksDock._reload_base_data(stub)
    assert stub.pipes_by_code[code].bob2 == before.bob2 - 1.0


def test_on_base_edited_reloads_and_rebuilds(fixtures_dir, tmp_gpkg):
    """Committen van laag-edits moet de basisdata verversen én hertekenen."""
    from drainworks_plugin.ui.dock import DrainworksDock

    _base_gpkg(fixtures_dir, tmp_gpkg)
    stub = _stub(tmp_gpkg)
    calls = []
    stub.state = type("S", (), {"mark_base_edited": lambda self: calls.append("stale")})()
    stub._refresh_step_buttons = lambda: calls.append("buttons")
    stub._rebuild = lambda: calls.append("rebuild")
    DrainworksDock._on_base_edited(stub)
    assert stub.pipes_by_code            # basisdata opnieuw ingelezen
    assert "stale" in calls and "rebuild" in calls
