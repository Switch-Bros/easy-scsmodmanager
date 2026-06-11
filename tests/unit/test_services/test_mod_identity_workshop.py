"""Workshop-id and -url derivation from active_mods names."""

from easy_scsmodmanager.services.mod_identity import (
    workshop_id_from_active_name,
    workshop_url_from_active_name,
)


def test_decodes_hex_tail_to_decimal_id() -> None:
    assert workshop_id_from_active_name("mod_workshop_package.000000003A4B7C12") == "978025490"


def test_non_workshop_names_give_none() -> None:
    assert workshop_id_from_active_name("promods") is None
    assert workshop_id_from_active_name("mod_workshop_package.NOTHEX") is None
    assert workshop_id_from_active_name("mod_workshop_package.AB.CD") is None


def test_url_for_workshop_name() -> None:
    url = workshop_url_from_active_name("mod_workshop_package.000000003A4B7C12")
    assert url == "https://steamcommunity.com/sharedfiles/filedetails/?id=978025490"


def test_url_for_local_name_is_none() -> None:
    assert workshop_url_from_active_name("local_mod") is None
