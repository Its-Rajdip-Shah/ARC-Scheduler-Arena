\
"""Meta-tests: make omissions from the contract suite visible.

This module does not test ARC behaviour.  It tests the *test suite*: every
frozen requirement in contract_manifest.py must be claimed by an executable
test, and every claimed ID must exist in the manifest.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .contract_manifest import REQUIREMENT_BY_ID, TEST_FILE_AREAS, ids_for_area


CONTRACT_DIR = Path(__file__).resolve().parent


def _literal_contract_ids_from_file(path: Path) -> set[str]:
    """Collect literal IDs from @covers("ID", ...) decorators without importing tests."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            is_covers = (
                isinstance(func, ast.Name) and func.id == "covers"
            ) or (
                isinstance(func, ast.Attribute) and func.attr == "covers"
            )
            if not is_covers:
                continue

            for arg in decorator.args:
                assert isinstance(arg, ast.Constant) and isinstance(arg.value, str), (
                    f"{path.name}:{node.lineno}: @covers arguments must be literal "
                    "contract-ID strings so coverage can be audited statically."
                )
                found.add(arg.value)

    return found


def _all_claimed_ids() -> dict[str, set[str]]:
    claims: dict[str, set[str]] = {}
    for path in sorted(CONTRACT_DIR.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        claims[path.name] = _literal_contract_ids_from_file(path)
    return claims


def test_manifest_ids_are_unique_and_well_formed():
    ids = list(REQUIREMENT_BY_ID)
    assert len(ids) == len(set(ids))
    assert ids
    for requirement_id in ids:
        prefix, sep, number = requirement_id.partition("-")
        assert sep == "-" and prefix.isalpha() and number.isdigit(), requirement_id


def test_expected_contract_test_files_exist():
    missing = [
        filename
        for filename in TEST_FILE_AREAS
        if not (CONTRACT_DIR / filename).is_file()
    ]
    assert not missing, (
        "Frozen ARC contract suite is incomplete. Missing test modules: "
        + ", ".join(missing)
    )


def test_every_claimed_requirement_id_exists():
    unknown: dict[str, list[str]] = {}
    for filename, claimed in _all_claimed_ids().items():
        bad = sorted(claimed - REQUIREMENT_BY_ID.keys())
        if bad:
            unknown[filename] = bad
    assert not unknown, f"Tests claim unknown ARC contract IDs: {unknown}"


def test_each_contract_area_is_claimed_by_its_designated_test_file():
    """Each contract area must be covered across its designated test module(s).

    Multiple files may intentionally share an area.  For example, round-trip
    behaviour is split between test_19_round_trip.py and
    test_20_state_machine_torture.py, so their claims must be combined rather
    than requiring both files to duplicate every RT requirement.
    """
    area_files: dict[str, set[str]] = {}

    for filename, areas in TEST_FILE_AREAS.items():
        for area in areas:
            area_files.setdefault(area, set()).add(filename)

    problems: dict[str, dict[str, list[str]]] = {}

    for area, filenames in area_files.items():
        claimed: set[str] = set()

        for filename in filenames:
            path = CONTRACT_DIR / filename
            if not path.exists():
                # The existence test provides the cleaner primary failure.
                continue
            claimed |= _literal_contract_ids_from_file(path)

        required = ids_for_area(area)
        missing = sorted(required - claimed)

        if missing:
            problems[area] = {
                "designated_files": sorted(filenames),
                "missing_contract_ids": missing,
            }

    assert not problems, (
        "Some frozen requirements have no test in their designated contract "
        f"area: {problems}"
    )


def test_every_frozen_requirement_is_covered_somewhere():
    all_claimed = set().union(*_all_claimed_ids().values()) if _all_claimed_ids() else set()
    missing = sorted(REQUIREMENT_BY_ID.keys() - all_claimed)
    assert not missing, (
        "Contract requirements without executable tests: "
        + ", ".join(missing)
    )
