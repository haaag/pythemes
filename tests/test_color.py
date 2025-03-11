from __future__ import annotations

from typing import NamedTuple

import pytest
from pytest import MonkeyPatch

from pythemes.__main__ import BLUE
from pythemes.__main__ import BOLD
from pythemes.__main__ import CYAN
from pythemes.__main__ import END
from pythemes.__main__ import GRAY
from pythemes.__main__ import GREEN
from pythemes.__main__ import ITALIC
from pythemes.__main__ import MAGENTA
from pythemes.__main__ import RED
from pythemes.__main__ import UNDERLINE
from pythemes.__main__ import YELLOW
from pythemes.__main__ import colorize


class ColorCase(NamedTuple):
    name: str
    text: str
    styles: list[str]
    expected: str


@pytest.mark.parametrize(
    ('name', 'text', 'styles', 'expected'),
    (
        ColorCase(
            name='bold',
            text='text',
            styles=[BOLD],
            expected=f'{BOLD}text{END}',
        ),
        ColorCase(
            name='bold_italic_red',
            text='text',
            styles=[BOLD, ITALIC, RED],
            expected=f'{BOLD}{ITALIC}{RED}text{END}',
        ),
        ColorCase(
            name='blue_italic_underline',
            text='text',
            styles=[BLUE, ITALIC, UNDERLINE],
            expected=f'{BLUE}{ITALIC}{UNDERLINE}text{END}',
        ),
        ColorCase(
            name='cyan_bold_italic',
            text='text',
            styles=[CYAN, BOLD, ITALIC],
            expected=f'{CYAN}{BOLD}{ITALIC}text{END}',
        ),
        ColorCase(
            name='gray_italic',
            text='text',
            styles=[GRAY, ITALIC],
            expected=f'{GRAY}{ITALIC}text{END}',
        ),
        ColorCase(
            name='yellow_underline',
            text='text',
            styles=[YELLOW, UNDERLINE],
            expected=f'{YELLOW}{UNDERLINE}text{END}',
        ),
        ColorCase(
            name='green_italic',
            text='text',
            styles=[GREEN, ITALIC],
            expected=f'{GREEN}{ITALIC}text{END}',
        ),
        ColorCase(
            name='magenta_bold',
            text='text',
            styles=[MAGENTA, BOLD],
            expected=f'{MAGENTA}{BOLD}text{END}',
        ),
        ColorCase(
            name='none',
            text='text',
            styles=[],
            expected='text',
        ),
    ),
)
def test_color_fn(name: str, text: str, styles: list[str], expected: str) -> None:
    from pythemes.__main__ import SysOps

    SysOps.color = True
    got = colorize(text, *styles)
    assert got == expected, f'failed for {name}: {expected=} {got=}'


@pytest.mark.parametrize(
    ('name', 'text', 'styles', 'expected'),
    (
        ColorCase(
            name='bold',
            text='text',
            styles=[BOLD],
            expected='text',
        ),
        ColorCase(
            name='bold_italic_red',
            text='text',
            styles=[BOLD, ITALIC, RED],
            expected='text',
        ),
        ColorCase(
            name='blue_italic_underline',
            text='text',
            styles=[BLUE, ITALIC, UNDERLINE],
            expected='text',
        ),
        ColorCase(
            name='cyan_bold_italic',
            text='text',
            styles=[CYAN, BOLD, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='gray_italic',
            text='text',
            styles=[GRAY, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='yellow_underline',
            text='text',
            styles=[YELLOW, UNDERLINE],
            expected='text',
        ),
        ColorCase(
            name='green_italic',
            text='text',
            styles=[GREEN, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='magenta_bold',
            text='text',
            styles=[MAGENTA, BOLD],
            expected='text',
        ),
        ColorCase(
            name='none',
            text='text',
            styles=[],
            expected='text',
        ),
    ),
)
def test_color_fn_no_color(name: str, text: str, styles: list[str], expected: str) -> None:
    from pythemes.__main__ import SysOps

    SysOps.color = False
    assert colorize(text, *styles) == expected, f'failed for {name}'


@pytest.mark.parametrize(
    ('name', 'text', 'styles', 'expected'),
    (
        ColorCase(
            name='bold',
            text='text',
            styles=[BOLD],
            expected='text',
        ),
        ColorCase(
            name='bold_italic_red',
            text='text',
            styles=[BOLD, ITALIC, RED],
            expected='text',
        ),
        ColorCase(
            name='blue_italic_underline',
            text='text',
            styles=[BLUE, ITALIC, UNDERLINE],
            expected='text',
        ),
        ColorCase(
            name='cyan_bold_italic',
            text='text',
            styles=[CYAN, BOLD, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='gray_italic',
            text='text',
            styles=[GRAY, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='yellow_underline',
            text='text',
            styles=[YELLOW, UNDERLINE],
            expected='text',
        ),
        ColorCase(
            name='green_italic',
            text='text',
            styles=[GREEN, ITALIC],
            expected='text',
        ),
        ColorCase(
            name='magenta_bold',
            text='text',
            styles=[MAGENTA, BOLD],
            expected='text',
        ),
        ColorCase(
            name='none',
            text='text',
            styles=[],
            expected='text',
        ),
    ),
)
def test_color_no_color_env(
    name: str,
    text: str,
    styles: list[str],
    expected: str,
    monkeypatch: MonkeyPatch,
):
    from pythemes.__main__ import SysOps

    SysOps.color = True
    monkeypatch.setenv('NO_COLOR', '1')

    assert colorize(text, *styles) == expected, f'failed for {name}'
