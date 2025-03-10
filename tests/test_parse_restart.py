from __future__ import annotations

import configparser
from typing import NamedTuple

import pytest

from pythemes.__main__ import parse_restart


class Case(NamedTuple):
    name: str
    config_data: dict[str, dict[str, str]]
    expected_programs: list[str]
    expected_section: bool


@pytest.mark.parametrize(
    ('name', 'config_data', 'expected_programs', 'expected_section'),
    (
        Case(
            name='valid_restart_section',
            config_data={'restart': {'cmd': 'vim tmux htop'}},
            expected_programs=[],
            expected_section=False,
        ),
        Case(
            name='missing_restart_section',
            config_data={},
            expected_programs=[],
            expected_section=False,
        ),
        Case(
            name='empty_cmd_field',
            config_data={'restart': {'cmd': ''}},
            expected_programs=[],
            expected_section=False,
        ),
    ),
)
def test_parse_restart(name, config_data, expected_programs, expected_section):
    config = configparser.ConfigParser()

    # populate config with test data
    for section, options in config_data.items():
        config.add_section(section)
        for key, value in options.items():
            config.set(section, key, value)

    programs = []

    parse_restart(config)

    assert programs == expected_programs, (
        f'{name}: parsed programs do not match expected'
    )
    assert config.has_section('restart') == expected_section, (
        f'{name}: section removal mismatch'
    )
