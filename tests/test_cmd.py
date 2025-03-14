from __future__ import annotations

import pytest

from pythemes.__main__ import ModeAction
from tests.conftest import CONFIG


@pytest.fixture()
def tmp_modeaction() -> ModeAction:
    return ModeAction.new(
        {
            'name': 'dunst-reload',
            'light': CONFIG.light,
            'dark': CONFIG.dark,
            'cmd': CONFIG.cmd,
        },
        dry_run=True,
    )


def test_modeaction_get_mode(tmp_modeaction: ModeAction):
    cmd = tmp_modeaction
    dark_mode = cmd.get_mode('dark')
    assert dark_mode == CONFIG.dark, f'dark mode: want: {CONFIG.dark!r}, got: {dark_mode!r}'
    assert dark_mode == tmp_modeaction.dark, (
        f'dark mode: want: {tmp_modeaction.dark!r}, got: {dark_mode!r}'
    )
    light_mode = cmd.get_mode('light')
    assert light_mode == tmp_modeaction.light, (
        f'light mode: want: {tmp_modeaction.light!r}, got: {light_mode!r}'
    )
    assert light_mode == CONFIG.light, f'light mode: want: {CONFIG.light!r}, got: {light_mode!r}'

    nonexistentmode = 'nonexistentmode'
    with pytest.raises(ValueError, match=rf'invalid mode {nonexistentmode!r}'):
        cmd.get_mode(nonexistentmode)
