from drainworks_plugin.sideview.settings import SideViewSettings


def test_defaults_and_roundtrip_dict():
    s = SideViewSettings()
    assert s.legend_position == "top-left"
    assert s.show_putcodes is True
    d = s.to_dict()
    s2 = SideViewSettings.from_dict(d)
    assert s2.line_width == s.line_width
    assert s2.legend_white_bg == s.legend_white_bg


def test_from_dict_tolerates_missing_keys():
    s = SideViewSettings.from_dict({"line_width": 3})
    assert s.line_width == 3
    assert s.legend_position == "top-left"
