from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from tests.conftest import THEME_NAME

if TYPE_CHECKING:
    import pytest

    from pythemes.__main__ import App
    from pythemes.__main__ import ModeAction
    from pythemes.__main__ import Theme


def test_theme_init(theme: Theme, caplog: pytest.LogCaptureFixture):
    assert theme.name == THEME_NAME
    theme.parse_apps()
    assert theme.inifile.filepath.exists()
    assert theme.wallpaper.has
    assert len(theme.cmds) == 1
    assert len(theme.apps) == 2  # noqa: PLR2004
    assert len(caplog.text) == 0


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
