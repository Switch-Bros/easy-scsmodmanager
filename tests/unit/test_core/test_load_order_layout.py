from easy_scsmodmanager.core.load_order_layout import ModRow, SpacerRow, build_rows


def test_empty_shows_all_spacers_in_order():
    rows = build_rows([])
    assert all(isinstance(r, SpacerRow) for r in rows)
    assert [r.group_id for r in rows] == [
        "map_base",
        "graphics_weather",
        "sound",
        "physics",
        "ui_other",
        "tuning_interior",
        "ai_traffic",
        "cargo",
        "paint_jobs",
        "trailers",
        "trucks",
        "maps",
    ]


def test_single_sound_mod_gets_preceding_spacers():
    rows = build_rows([("snd", "sound")])
    head = rows[:4]
    assert isinstance(head[0], SpacerRow) and head[0].group_id == "map_base"
    assert isinstance(head[1], SpacerRow) and head[1].group_id == "graphics_weather"
    assert isinstance(head[2], SpacerRow) and head[2].group_id == "sound"
    assert isinstance(head[3], ModRow) and head[3].mod == "snd" and head[3].misplaced is False
    assert sum(1 for r in rows if isinstance(r, SpacerRow)) == 12


def test_misplaced_mod_flagged_not_reordered():
    rows = build_rows([("map1", "map"), ("snd", "sound")])
    mods = [(r.mod, r.misplaced) for r in rows if isinstance(r, ModRow)]
    assert mods == [("map1", False), ("snd", True)]


def test_two_mods_same_group_one_spacer():
    rows = build_rows([("t1", "truck"), ("t2", "truck")])
    trucks_spacers = [r for r in rows if isinstance(r, SpacerRow) and r.group_id == "trucks"]
    assert len(trucks_spacers) == 1
    mods = [(r.mod, r.misplaced) for r in rows if isinstance(r, ModRow)]
    assert mods == [("t1", False), ("t2", False)]


def test_modrow_reports_expected_group():
    rows = build_rows([("snd", "sound")])
    mod_row = next(r for r in rows if isinstance(r, ModRow))
    assert mod_row.expected_group_id == "sound"
