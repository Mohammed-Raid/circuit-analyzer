"""@file test_ui_kit.py
@brief Tests TDD pour gui/ui_kit.py (widget factories)."""
import os

import pytest

os.environ.setdefault("DISPLAY", "")  # no-op Windows
ctk = pytest.importorskip("customtkinter")
from gui import ui_kit


@pytest.fixture(scope="module")
def root():
    r = ctk.CTk()
    r.withdraw()
    yield r
    r.destroy()


def test_font_roles(root):
    f = ui_kit.font("title")
    assert f.cget("size") == 18


def test_font_body(root):
    f = ui_kit.font("body")
    assert f.cget("size") == 13


def test_font_overline(root):
    f = ui_kit.font("overline")
    assert f.cget("size") == 9
    assert f.cget("weight") == "bold"


def test_icon_returns_image(root):
    img = ui_kit.icon("search")
    assert isinstance(img, ctk.CTkImage)


def test_icon_cached(root):
    img1 = ui_kit.icon("search")
    img2 = ui_kit.icon("search")
    assert img1 is img2


def test_icon_color_param_ignored(root):
    # color= is accepted but ignored (YAGNI — PNGs already tinted)
    img = ui_kit.icon("search", size=20, color="#ff0000")
    assert isinstance(img, ctk.CTkImage)


def test_factories_build(root):
    assert ui_kit.Card(root)
    assert ui_kit.StatCard(root, "17", "Composants", "cpu", "#3b82f6")
    assert ui_kit.PrimaryButton(root, "OK", lambda: None)
    assert ui_kit.SecondaryButton(root, "Sec", lambda: None)
    assert ui_kit.GhostButton(root, "Annuler", lambda: None)
    assert ui_kit.DangerButton(root, "Sup", lambda: None)
    assert ui_kit.IconButton(root, "trash-2", lambda: None)
    assert ui_kit.SectionHeader(root, "MENU")
    assert ui_kit.Field(root, placeholder="chemin…")


def test_primary_button_with_icon(root):
    btn = ui_kit.PrimaryButton(root, "Ouvrir", lambda: None, icon_name="folder-open")
    assert isinstance(btn, ctk.CTkButton)


def test_card_is_frame(root):
    card = ui_kit.Card(root)
    assert isinstance(card, ctk.CTkFrame)


def test_section_header_is_label(root):
    lbl = ui_kit.SectionHeader(root, "SECTION")
    assert isinstance(lbl, ctk.CTkLabel)


def test_field_is_entry(root):
    entry = ui_kit.Field(root, placeholder="test")
    assert isinstance(entry, ctk.CTkEntry)
