from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from pythemes.__main__ import INIFile
from pythemes.__main__ import INISection


def test_parse(ini_filepath: Path):
    ini = INIFile(ini_filepath).read().parse()
    assert 'wallpaper' in ini.data
    assert 'wallpaper' not in ini.config
    assert not ini.config.has_section('wallpaper')


def test_has_section(ini_filepath: Path):
    section = 'test_program'
    ini = INIFile(ini_filepath).read().parse()
    assert ini.config.has_section(section)
    assert ini.config.has_option(section, 'query')


def test_add_section(ini_filepath: Path):
    section = 'test_program'
    ini = INIFile(ini_filepath).read().parse()
    ini.add('restart', {'cmd': ''})
    assert ini.config.has_section('restart')
    assert ini.config.has_section(section)


def test_raises_nosectionserr(temp_ini):
    filepath = temp_ini('test', '')
    ini = INIFile(filepath)
    with pytest.raises(configparser.NoSectionError):
        ini.read()


def test_raises_filenotfounderr():
    f = Path('/nonexistent/file.ini')
    with pytest.raises(FileNotFoundError):
        ini = INIFile(f)
        ini.read()


def test_parse_data(ini_filepath: Path, temp_section: INISection):
    section = 'test_program'
    ini = INIFile(ini_filepath).read()
    ini.add(section + '_new', temp_section).parse()
    assert len(ini.data) != 0
    assert len(ini.data) == len(ini.config.sections()) + 1
    assert ini.data[section]['light'] == 'light'
    assert ini.data['test_program']['cmd'] == 'run-test'


def test_get_section_success(ini_filepath: Path):
    ini = INIFile(ini_filepath).read().parse()
    section = ini.get('test_program')
    assert section is not None
    assert section == {
        'file': section.get('file'),
        'query': 'export GLOBAL_THEME={theme}',
        'light': 'light',
        'dark': 'dark',
        'cmd': 'run-test',
    }
    # non existent section
    nonexistent = ini.get('nonexistent')
    assert nonexistent is None


def test_parse_restart_section(ini_filepath: Path):
    ini = INIFile(ini_filepath).read().parse()
    section = 'restart'
    ini.add(section, {'cmd': ''})
    assert section not in ini.data
