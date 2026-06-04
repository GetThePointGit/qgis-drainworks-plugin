from drainworks_plugin.sideview.settings import LINE_DEFAULTS, SideViewSettings


def test_defaults():
    s = SideViewSettings()
    assert s.legend_position == "top-left"
    assert s.legend_white_bg is True          # white background on by default
    assert s.show_putcodes is True
    assert s.line("bob")["color"] == "#333333"
    assert s.line("water")["width"] == 1
    assert set(s.lines) == set(LINE_DEFAULTS)


def test_roundtrip_dict():
    s = SideViewSettings()
    s.lines["bob"]["color"] = "#ff0000"
    s.lines["bob"]["width"] = 4
    s2 = SideViewSettings.from_dict(s.to_dict())
    assert s2.line("bob") == {"color": "#ff0000", "width": 4}
    assert s2.legend_white_bg is True


def test_from_dict_fills_missing_lines_and_keys():
    s = SideViewSettings.from_dict({"lines": {"bob": {"color": "#123456"}}})
    assert s.line("bob")["color"] == "#123456"
    assert s.line("bob")["width"] == LINE_DEFAULTS["bob"]["width"]   # filled
    assert s.line("maaiveld") == LINE_DEFAULTS["maaiveld"]           # whole line filled


def test_from_dict_ignores_legacy_flat_keys():
    s = SideViewSettings.from_dict({"line_color": "#000000", "line_width": 9})
    assert s.line("bob") == LINE_DEFAULTS["bob"]   # legacy keys ignored, defaults used
