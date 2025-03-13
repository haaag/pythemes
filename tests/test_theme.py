from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from tests.conftest import CONFIG

if TYPE_CHECKING:
    from pythemes.__main__ import App
    from pythemes.__main__ import INISection
    from pythemes.__main__ import ModeAction
    from pythemes.__main__ import Theme


def test_theme_init(theme: Theme):
    assert theme.name == CONFIG.name
    theme.parse_apps()
    assert theme.inifile.filepath.exists()
    assert hasattr(theme, 'wallpaper')
    assert len(theme.cmds) == 1
    assert len(theme.apps) == 2  # noqa: PLR2004


def test_theme_register(theme: Theme, valid_app: App, valid_cmd: ModeAction):
    toappend = 5
    other_app = copy.deepcopy(valid_app)
    other_app.name = 'other_app'

    # apps
    assert len(theme.apps) == 0
    for _ in range(toappend):
        theme.register_app(valid_app)
        theme.register_app(other_app)
    # ignore duplicates
    assert len(theme.apps) == 2  # noqa: PLR2004

    # commands
    assert len(theme.cmds) == 0
    for _ in range(toappend):
        theme.register_cmd(valid_cmd)
    assert len(theme.cmds) == toappend


def test_theme_errors(theme: Theme, temp_section: INISection):
    expected_errors = 3
    assert theme.errors() == 0
    for i in range(expected_errors):
        temp_section['query'] = f'invalid_query {i}'
        theme.inifile.add(f'invalid_section_{i}', temp_section)
    theme.parse_apps()
    assert theme.errors() == expected_errors


def test_theme_get(theme: Theme):
    target_app = 'xresources'
    theme.parse_apps()
    app = theme.get(target_app)
    assert app is not None
    assert app.name == target_app
    nonexistent_app = 'nonexistent'
    app = theme.get(nonexistent_app)
    assert app is None
