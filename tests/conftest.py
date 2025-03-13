from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Callable
from typing import NamedTuple

import pytest

from pythemes.__main__ import App
from pythemes.__main__ import INIFile
from pythemes.__main__ import ModeAction
from pythemes.__main__ import Theme
from pythemes.__main__ import Wallpaper

if TYPE_CHECKING:
    from pathlib import Path

    from pythemes.__main__ import INISection


class ConfigForTest(NamedTuple):
    name: str
    light: str
    dark: str
    query: str
    cmd: str


CONFIG = ConfigForTest(
    name='gruvbox',
    light='gruvbox-light',
    dark='gruvbox-dark',
    query='export BAT_THEME="{}"',
    cmd='run-test',
)


@pytest.fixture
def temp_content_with_valid_files(tmp_path: Path) -> str:
    test_program_file = tmp_path / 'env.sh'
    test_program_file.write_text('some text\nsome comment\nexport GLOBAL_THEME={theme}')
    test_program_file.touch()
    test_xresources_file = tmp_path / 'xresources.theme'
    test_xresources_file.write_text(
        'some text\nsome comment\n#define CURRENT_THEME GRUVBOX_LIGHT_MEDIUM'
    )
    test_xresources_file.touch()
    return f"""\
    [wallpaper]
    light=/path/to/light.jpg
    dark=/path/to/dark.jpg
    random=/path/to/wallpapers/
    cmd=feh --bg-scale

    [test_program]
    file={test_program_file.as_posix()}
    query=export GLOBAL_THEME={{theme}}
    light=light
    dark=dark
    cmd=run-test

    [xresources]
    file={test_xresources_file.as_posix()}
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
def temp_section(temp_file: Callable[..., Path]) -> INISection:
    file = temp_file('value1.txt', 'value2\nvalue3\nquery gruvbox-light')
    return {
        'name': 'app_name',
        'file': file.as_posix(),
        'query': 'query {theme}',
        'dark': 'gruvbox-dark',
        'light': 'gruvbox-light',
        'cmd': 'value4',
    }


@pytest.fixture
def temp_ini(tmp_path):
    def create_ini(filename, content) -> Path:
        path = tmp_path / f'{filename}.ini'
        path.write_text(content)
        return path

    return create_ini


@pytest.fixture
def ini_filepath(tmp_path: Path, temp_content_with_valid_files: str) -> Path:
    """
    Creates a temporary INI file with sample data and returns an INIFile instance.
    """
    content = temp_content_with_valid_files
    ini_path = tmp_path / f'{CONFIG.name}.ini'
    ini_path.write_text(content, encoding='utf-8')
    return ini_path


@pytest.fixture
def theme(ini_filepath: Path) -> Theme:
    ini = INIFile(ini_filepath).read().parse()
    return Theme(CONFIG.name, ini, dry_run=True)


@pytest.fixture
def valid_app(temp_section: INISection) -> App:
    return App.new(temp_section, dry_run=True)


@pytest.fixture
def valid_app_with_file_and_content(temp_file: Callable[..., Path]) -> Callable[..., App]:
    def create_app(filename, current_theme, content):
        target_file = temp_file(filename, content)
        app = App.new(
            {
                'name': 'test_app',
                'file': target_file.as_posix(),
                'query': 'export BAT_THEME="{theme}"',
                'dark': 'gruvbox-dark',
                'light': current_theme,
            },
            dry_run=True,
        )
        assert app.path == target_file
        return app

    return create_app


@pytest.fixture
def valid_app_with_file(temp_file: Callable[..., Path]) -> App:
    current_theme = 'gruvbox-light'
    target_file = temp_file(
        'filetemp.conf',
        f'export ANOTHER=null\nexport BAT_THEME="{current_theme}"\n',
    )
    app = App.new(
        {
            'name': 'test_app',
            'file': target_file.as_posix(),
            'query': 'export BAT_THEME="{theme}"',
            'dark': 'gruvbox-dark',
            'light': current_theme,
        },
        dry_run=True,
    )
    assert app.path == target_file
    return app


@pytest.fixture
def valid_cmd() -> ModeAction:
    return ModeAction.new(
        {
            'name': 'test',
            'light': 'gruvbox.light',
            'dark': 'gruvbox.dark',
            'cmd': 'gruvbox -r',
        },
        dry_run=True,
    )


@pytest.fixture
def temp_wall(temp_wall_files: dict[str, Path]) -> Wallpaper:
    f = temp_wall_files
    return Wallpaper(
        dark=f['dark'],
        light=f['light'],
        random=f['random'],
        cmd='nitrogen --save --set-zoom-fill',
        dry_run=True,
    )
