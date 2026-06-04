from drainworks_plugin.io.import_controller import import_to_base

import rgs_ribx  # noqa: F401


def test_import_ribx_to_base_writes_layers(fixtures_dir, tmp_gpkg):
    out = import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg))
    assert str(out) == str(tmp_gpkg)

    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert {"manholes", "pipes", "measurements_raw"} <= names
    assert ds.GetLayerByName("measurements_raw").GetFeatureCount() == 3


def test_import_to_base_no_heights_yet(fixtures_dir, tmp_gpkg):
    import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg))
    from osgeo import ogr
    ds = ogr.Open(str(tmp_gpkg))
    names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
    assert "profile" not in names and "segments" not in names


def test_import_to_base_reports_phases(fixtures_dir, tmp_gpkg):
    phases = []
    import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg),
                   on_phase=phases.append)
    # An "inlezen" (read) phase before a "wegschrijven" (write) phase, then done.
    assert any("inlezen" in p.lower() for p in phases)
    assert any("wegschrijven" in p.lower() for p in phases)
    assert phases[-1] == "Klaar"


def test_import_to_base_phase_callback_errors_are_ignored(fixtures_dir, tmp_gpkg):
    def boom(_text):
        raise RuntimeError("callback should not break the import")

    out = import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg),
                         on_phase=boom)
    assert str(out) == str(tmp_gpkg)
