from __future__ import annotations

import copy
from typing import Callable

import pytest

from pythemes.__main__ import App
from pythemes.__main__ import Cmd
from pythemes.__main__ import INISection
from pythemes.__main__ import ThemeModeError
from pythemes.__main__ import process_app
from tests.conftest import CONFIG


def test_app_new(temp_section: INISection):
    app = App.new(temp_section, dry_run=True)
    assert app.file == temp_section['file']
    assert app.dark == temp_section['dark']
    assert app.light == temp_section['light']
    assert isinstance(app.cmd, Cmd)


def test_app_validate(valid_app: App):
    valid_app.validate()
    assert not valid_app.error.occurred


def test_app_filenotfound(valid_app: App):
    valid_app.file = 'nonexistentfile.conf'
    with pytest.raises(FileNotFoundError):
        valid_app.has_changes('nonexistentmode')


def test_app_do_not_has_changes(valid_app_with_file: App):
    app = valid_app_with_file
    assert not app.has_changes('light')
    assert app.has_changes('dark')


def test_app_find_current_theme(valid_app_with_file_and_content: Callable[..., App]):
    current_theme = CONFIG.light
    current_theme_idx = 2
    lines = ['export VAR=1', 'export PAGER=less', f'export BAT_THEME="{current_theme}"']
    app = valid_app_with_file_and_content('file.conf', CONFIG.light, '\n'.join(lines))
    idx, got_current_theme = app.find_current_theme()
    assert app.has_changes('dark')
    assert idx == current_theme_idx
    assert got_current_theme == current_theme


def test_app_determine_next_theme(valid_app_with_file_and_content: Callable[..., App]):
    current_theme = CONFIG.query.format(CONFIG.light)
    next_theme = CONFIG.query.format(CONFIG.dark)
    lines = ['export VAR=1', 'export PAGER=less', current_theme]
    app = valid_app_with_file_and_content('file.conf', CONFIG.light, '\n'.join(lines))
    _, got_current_theme = app.find_current_theme()
    assert got_current_theme is not None
    assert app.determine_next_theme(got_current_theme, 'dark') == next_theme
    with pytest.raises(ThemeModeError):
        app.determine_next_theme(got_current_theme, 'nonexistentmode')


def test_app_get_mode(valid_app: App):
    assert valid_app.get_mode(mode='light') == CONFIG.light
    assert valid_app.get_mode(mode='dark') == CONFIG.dark
    assert valid_app.get_mode(mode='nonexistentmode') is None


def test_app_update(valid_app_with_file: App):
    mode = 'dark'
    index = 1
    app = valid_app_with_file
    assert app.has_changes(mode)
    app.dry_run = False
    original_lines = copy.deepcopy(app.lines)
    app.update(mode)
    assert app.lines != original_lines, 'lines not updated'
    with app.path.open(mode='r', encoding='utf-8') as file:
        modified_lines = file.read().splitlines()
        assert modified_lines[index] == app.lines[index].strip()


@pytest.mark.parametrize(
    'field, value, expected_err_mesg',
    [
        ('file', '', 'no file specified.'),
        ('file', 'file.txt', "filepath 'file.txt' do not exists."),
        ('query', 'invalid-query', "query does not contain placeholder '{theme}'."),
        ('dark', '', 'no dark theme specified.'),
        ('light', '', 'no light theme specified.'),
        ('query', '', 'no query specified.'),
    ],
)
def test_app_invalid(
    valid_app: App, field: str, value: str, expected_err_mesg: str, caplog: pytest.LogCaptureFixture
):
    app = copy.deepcopy(valid_app)
    # set the invalid attribute
    setattr(app, field, value)
    app.validate()
    assert app.error.occurred
    assert app.error.mesg == expected_err_mesg
    process_app(app, 'dark')
    mesg_got = caplog.record_tuples[0][2]
    assert mesg_got == f'{app.name}: {app.error.mesg}', (
        f'want: {expected_err_mesg!r}, got: {mesg_got!r}'
    )
