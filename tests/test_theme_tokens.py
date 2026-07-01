from gui import theme


def test_token_families_present():
    for name in ("BG", "SURFACE", "RAISED", "OVERLAY", "BORDER", "BORDER_SOFT",
                 "TEXT", "TEXT_MUTED", "TEXT_DIM", "BLUE", "BLUE_HOVER", "BLUE_PRESS",
                 "BLUE_SOFT", "CYAN", "SUCCESS", "WARN", "ERROR", "INFO"):
        v = getattr(theme, name)
        assert isinstance(v, str) and v.startswith("#") and len(v) == 7, name


def test_scales_are_ordered():
    assert list(theme.SP.values()) == sorted(theme.SP.values())
    assert list(theme.R.values()) == sorted(theme.R.values())
    assert set(theme.TYPE) >= {"display", "title", "body", "caption", "overline"}


def test_backcompat_aliases():
    assert theme.CARD == theme.RAISED
    assert theme.MUTED == theme.TEXT_DIM
    assert theme.BLUE_D == theme.BLUE_PRESS
