import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "build_countries", Path(__file__).parent.parent / "scripts" / "build_countries.py"
)
build_countries = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_countries)
build_table = build_countries.build_table


def country(cca2, currencies=("XXX",), root="+6", suffixes=("6",)):
    return {
        "cca2": cca2,
        "currencies": {c: {} for c in currencies},
        "idd": {"root": root, "suffixes": list(suffixes)},
    }


def test_single_suffix_calling_code():
    table = build_table([country("TH", ("THB",), "+6", ("6",))], {"0066"})
    assert table["TH"] == {"currency": "THB", "mofa_code": "0066"}


def test_multi_digit_suffix():
    table = build_table([country("IS", ("ISK",), "+3", ("54",))], {"0354"})
    assert table["IS"]["mofa_code"] == "0354"
    assert build_table([country("IS", ("ISK",), "+3", ("54",))], set())["IS"]["mofa_code"] is None


def test_us_and_canada_overrides():
    many = [str(n) for n in range(201, 210)]
    table = build_table(
        [country("US", ("USD",), "+1", many), country("CA", ("CAD",), "+1", many)], {"1000", "9001"}
    )
    assert table["US"] == {"currency": "USD", "mofa_code": "1000"}
    assert table["CA"] == {"currency": "CAD", "mofa_code": "9001"}


def test_no_currency_is_null():
    assert build_table([country("AQ", (), "", ())], set())["AQ"] == {"currency": None, "mofa_code": None}


def test_calling_code_not_in_mofa_list_is_null():
    assert build_table([country("XX", ("XXX",), "+9", ("99",))], {"0066"})["XX"]["mofa_code"] is None


def test_first_currency_is_used():
    assert build_table([country("ZW", ("USD", "ZWL"), "+2", ("63",))], set())["ZW"]["currency"] == "USD"


def test_russia_override():
    table = build_table([country("RU", ("RUB",), "+7", ("3", "4", "5", "8", "9"))], {"9007"})
    assert table["RU"]["mofa_code"] == "9007"


def test_wrong_calling_code_excluded():
    # 合衆国領有小離島（UM）の電話番号データはエスワティニと重なるので、国番号を付けない
    table = build_table([country("UM", ("USD",), "+2", ("68",))], {"0268"})
    assert table["UM"]["mofa_code"] is None
