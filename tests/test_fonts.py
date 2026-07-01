from gui import fonts


def test_register_returns_a_family():
    fam = fonts.register_fonts()
    assert fam in ("Inter", "Segoe UI")
    assert fonts.FONT_FAMILY == fam
