from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pythemes.__main__ import App
from pythemes.__main__ import INIFile
from pythemes.__main__ import ModeAction
from pythemes.__main__ import Theme

if TYPE_CHECKING:
    from pathlib import Path

    from pythemes.__main__ import INISection

THEME_NAME = 'gruvbox'


@pytest.fixture
def temp_file(tmp_path):
    def create_file(filename, content):
        path = tmp_path / filename
        path.write_text(content)
        return path

    return create_file


@pytest.fixture
def temp_empty_file(tmp_path):
    def create_file(filename):
        return tmp_path / filename

    return create_file


@pytest.fixture
def temp_directory(tmp_path):
    def create_file(dirname):
        d = tmp_path / dirname
        d.mkdir()
        return d

    return create_file


@pytest.fixture
def temp_section() -> INISection:
    return {
        'name': 'app_name',
        'file': 'value1.txt',
        'query': 'query {theme}',
        'dark': 'value2',
        'light': 'valu3',
        'cmd': 'value4',
    }


@pytest.fixture
def temp_ini(tmp_path):
    def create_ini(name, content) -> Path:
        path = tmp_path / f'{name}.ini'
        path.write_text(content)
        return path

    return create_ini


@pytest.fixture
def ini_filepath(tmp_path: Path) -> Path:
    """
    Creates a temporary INI file with sample data and returns an INIFile instance.
    """
    prog_one = tmp_path / 'env.sh'
    prog_two = tmp_path / 'xresources.theme'
    prog_one.touch()
    prog_two.touch()
    content = f"""\
[wallpaper]
light=/path/to/light.jpg
dark=/path/to/dark.jpg
random=/path/to/wallpapers/
cmd=feh --bg-scale

[test_program]
file={prog_one.as_posix()}
query=export GLOBAL_THEME={{theme}}
light=light
dark=dark
cmd=run-test

[xresources]
file={prog_two.as_posix()}
query=#define CURRENT_THEME {{theme}}
light=GRUVBOX_LIGHT_MEDIUM
dark=GRUVBOX_DARK_MEDIUM
cmd=xrdb -load ~/.config/X11/xresources

[dunst-reload]
light=gruvbox.light
dark=gruvbox.dark
cmd=dunst-ts -s

[restart]
cmd = program1 program2
"""
    ini_path = tmp_path / f'{THEME_NAME}.ini'
    ini_path.write_text(content, encoding='utf-8')
    return ini_path


@pytest.fixture
def theme(ini_filepath: Path) -> Theme:
    ini = INIFile(ini_filepath).read().parse()
    return Theme(THEME_NAME, ini, dry_run=True)


@pytest.fixture
def valid_app(temp_section: INISection) -> App:
    return App.new(temp_section, dry_run=True)


@pytest.fixture
def valid_cmd() -> ModeAction:
    return ModeAction.new(
        {
            'name': 'test',
            'light': 'gruvbox.light',
            'dark': 'gruvbox.dark',
            'cmd': 'gruvbox -r',
        }
    )
