from __future__ import annotations

from typing import NamedTuple

import pytest

from pythemes.__main__ import find


class Case(NamedTuple):
    name: str
    query: str
    lines: list[str]
    expected: tuple[int, str] | type[Exception]


@pytest.mark.parametrize(
    ('name', 'query', 'lines', 'expected'),
    (
        Case(
            name='basic_match',
            query='theme-{theme}-config',
            lines=['theme-dark-config', 'theme-light-config'],
            expected=(0, 'dark'),
        ),
        Case(
            name='multiple_matches',
            query='theme-{theme}-config',
            lines=['random', 'theme-dark-config', 'theme-light-config'],
            expected=(1, 'dark'),
        ),
        Case(
            name='empty_list',
            query='theme-{theme}-config',
            lines=[],
            expected=(-1, ''),
        ),
        Case(
            name='special_characters',
            query='path/{theme}/file',
            lines=['path/admin/file', 'path/user/file'],
            expected=(0, 'admin'),
        ),
        Case(
            name='empty_query',
            query='',
            lines=['theme-dark-config', 'theme-light-config'],
            expected=(-1, ''),
        ),
        Case(
            name='partial_match',
            query='theme-{theme}',
            lines=['theme-dark-config', 'theme-light-config'],
            expected=(0, 'dark-config'),
        ),
        Case(
            name='no_match',
            query='export XDG_CACHE_HOME="$HOME"/.cache',
            lines=[
                'export EDITOR=nvim',
                'export XDG_DATA_HOME="$HOME"/.local/share',
                'export BAT_THEME="gruvbox-light"',
                'export BROWSER=firefox',
            ],
            expected=(-1, ''),
        ),
        Case(
            name='with_spaces',
            query='   export THEME={theme}',
            lines=[
                'export THEME=nvim',
                '   export THEME=nvim',
                'export THEME=nvim',
                'export XDG_DATA_HOME="$HOME"/.local/share',
                'export BAT_THEME="gruvbox-light"',
                'export BROWSER=firefox',
            ],
            expected=(1, 'nvim'),
        ),
        Case(
            name='no_placeholder',
            query='export EDITOR=nvim',
            lines=[
                'export EDITOR=nvim',
                'export EDITOR=nvim',
                '   export EDITOR=nvim',
                'export EDITOR=nvim',
                'export XDG_DATA_HOME="$HOME"/.local/share',
                'export BAT_THEME="gruvbox-light"',
                'export BROWSER=firefox',
            ],
            expected=(-1, ''),
        ),
    ),
)
def test_find(name, query, lines, expected):
    assert find(query, lines) == expected, f"Test case '{name}' failed"
