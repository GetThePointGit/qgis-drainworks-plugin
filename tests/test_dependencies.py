def test_rgs_ribx_importable():
    import rgs_ribx

    assert hasattr(rgs_ribx, "build_from_ribx")


def test_ogr_importable():
    from osgeo import ogr

    assert ogr.GetDriverByName("GPKG") is not None


def test_pyqtgraph_importable():
    import pyqtgraph  # noqa: F401
