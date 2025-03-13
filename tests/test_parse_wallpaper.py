from __future__ import annotations

import configparser
from typing import NamedTuple

import pytest

from pythemes.__main__ import INIData
from pythemes.__main__ import parse_wallpaper


class Case(NamedTuple):
    name: str
    config_data: dict[str, dict[str, str]]
    expected_data: INIData
    expected_section: bool


@pytest.mark.parametrize(
    ('name', 'config_data', 'expected_data', 'expected_section'),
    (
        Case(
            name='valid_wallpaper_section',
            config_data={
                'wallpaper': {
                    'light': '/path/to/light.jpg',
                    'dark': '/path/to/dark.jpg',
                    'random': '/path/to/wallpapers',
                    'cmd': 'feh --bg-scale',
                }
            },
            expected_data={
                'wallpaper': {
                    'light': '/path/to/light.jpg',
                    'dark': '/path/to/dark.jpg',
                    'random': '/path/to/wallpapers',
                    'cmd': 'feh --bg-scale',
                }
            },
            expected_section=False,
        ),
        Case(
            name='missing_wallpaper_section',
            config_data={},
            expected_data={},
            expected_section=False,
        ),
        Case(
            name='empty_cmd_field',
            config_data={
                'wallpaper': {
                    'light': '',
                    'dark': '',
                    'random': '',
                    'cmd': '',
                }
            },
            expected_data={
                'wallpaper': {
                    'light': '',
                    'dark': '',
                    'random': '',
                    'cmd': '',
                }
            },
            expected_section=False,
        ),
    ),
)
def test_parse_wallpaper(name, config_data, expected_data, expected_section):
    config = configparser.ConfigParser()
    for section, options in config_data.items():
        config.add_section(section)
        for key, value in options.items():
            config.set(section, key, value)

    data = {}
    parse_wallpaper(config, data)

    assert data == expected_data, f"Test '{name}' failed: Unexpected parsed data"
    assert config.has_section('wallpaper') == expected_section, (
        f"Test '{name}' failed: Section removal check failed"
    )
