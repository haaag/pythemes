from __future__ import annotations

from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest

from pythemes.__main__ import Files
from tests.conftest import THEME_NAME

FILE_CONTENT = """
[dunst-reload]
light=gruvbox.light
dark=gruvbox.dark
cmd=dunst-ts -s
"""


def test_file_mkdir_error(temp_file: Callable[..., Path]):
    fn = temp_file(filename=THEME_NAME, content=FILE_CONTENT)
    with pytest.raises(IsADirectoryError, match=rf'Cannot create directory: {fn!s} is a file.'):
        Files.mkdir(fn)


@pytest.mark.parametrize(
    'input_command, expected_output, name',
    [
        ('', '', 'empty'),
        ('ls -la', 'ls -la', 'ls'),
        ('echo ~', 'echo /home/user', 'tilde'),
        ('cat ~/.config/file.txt', 'cat /home/user/.config/file.txt', 'single expansion'),
        ('echo ~ && cd ~/projects', 'echo /home/user && cd /home/user/projects', 'doble expansion'),
        ('rm -rf ~/temp ~/backup', 'rm -rf /home/user/temp /home/user/backup', 'multiple paths'),
        ("echo '~' 'hello'", "echo '~' 'hello'", 'Quoted tilde should not expand'),
    ],
)
def test_files_expand_homepaths(input_command, expected_output, name):
    with patch.object(Path, 'expanduser', autospec=True) as mock_expanduser:
        mock_expanduser.side_effect = lambda self: Path(str(self).replace('~', '/home/user', 1))
        assert Files.expand_homepaths(input_command) == expected_output, f'failed {name!s}'


def test_files_readlines(ini_filepath: Path):
    text = ini_filepath.read_text(encoding='utf-8').splitlines()
    assert len(text) == len(Files.readlines(ini_filepath))


# def test_files_readlines_filenotfound(init
#


def test_files_savelines(temp_empty_file: Callable[..., Path]):
    data = ['line1\n', 'line2']
    fn = temp_empty_file(filename=THEME_NAME)
    Files.savelines(fn, data)
    assert len(fn.read_text(encoding='utf-8').splitlines()) == len(data)
