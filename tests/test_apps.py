from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING
from typing import Callable

import pytest

from pythemes.__main__ import App
from pythemes.__main__ import Cmd
from pythemes.__main__ import INISection
from pythemes.__main__ import logger

if TYPE_CHECKING:
    from pathlib import Path


def test_app_new(temp_section: INISection):
    app = App.new(temp_section, dry_run=True)
    assert app.file == 'value1.txt'
    assert app.dark == 'value2'
    assert app.light == 'valu3'
    assert isinstance(app.cmd, Cmd)


def test_app_validate(valid_app: App, temp_file: Callable[..., Path]):
    valid_app.file = temp_file(valid_app.file, '').as_posix()
    valid_app.validate()
    assert not valid_app.error.occurred


@pytest.mark.parametrize(
    'attr, value, log_message',
    [
        ('file', '', ': no file specified.'),
        ('file', 'file.txt', ": filepath '{file}' do not exists."),
        ('query', '', ': no query specified.'),
        ('query', 'query', ": query does not contain placeholder '{{theme}}'."),
        ('dark', '', ': no dark theme specified.'),
        ('light', '', ': no light theme specified.'),
    ],
)
def test_app_invalidaa(  # noqa: PLR0913
    valid_app: App,
    temp_file: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
    attr,
    value,
    log_message,
):
    invalid_app = copy.deepcopy(valid_app)
    invalid_app.file = temp_file(invalid_app.file, '').as_posix()
    # set the invalid attribute
    setattr(invalid_app, attr, value)
    expected_log = f'{invalid_app.name}{log_message.format(file=invalid_app.file)}'
    invalid_app.validate()
    assert invalid_app.error.occurred
    assert (logger.name, logging.WARNING, expected_log) in caplog.record_tuples


def test_app_newnew(temp_section: INISection):
    app = App.new(temp_section, dry_run=True)
    assert app.file == 'value1.txt'
    assert app.dark == 'value2'
    assert app.light == 'valu3'
    assert isinstance(app.cmd, Cmd)
