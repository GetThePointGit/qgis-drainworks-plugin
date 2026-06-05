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


def test_import_to_base_reports_progress(fixtures_dir, tmp_gpkg):
    marks = []
    import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg),
                   on_progress=lambda frac, label: marks.append((frac, label)))
    fracs = [f for f, _ in marks]
    labels = [lab for _, lab in marks]
    # Monotonic non-decreasing fractions in [0, 1], ending at 1.0 ("Klaar").
    assert fracs == sorted(fracs)
    assert all(0.0 <= f <= 1.0 for f in fracs)
    assert fracs[-1] == 1.0 and marks[-1][1] == "Klaar"
    assert any("inlezen" in lab.lower() for lab in labels)
    assert any("wegschrijven" in lab.lower() for lab in labels)


def test_import_to_base_progress_callback_errors_are_ignored(fixtures_dir, tmp_gpkg):
    def boom(_frac, _label):
        raise RuntimeError("callback should not break the import")

    out = import_to_base(str(fixtures_dir / "inclined.ribx"), None, str(tmp_gpkg),
                         on_progress=boom)
    assert str(out) == str(tmp_gpkg)
