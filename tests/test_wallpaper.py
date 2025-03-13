from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from pythemes.__main__ import InvalidFilePathError
from pythemes.__main__ import Wallpaper


@pytest.fixture
def temp_wall_files(temp_directory: Callable[..., Path]) -> dict[str, Path]:
    path = temp_directory('wallpaper')
    darkfile = path / 'dark.jpg'
    lightfile = path / 'light.jpg'
    darkfile.touch()
    lightfile.touch()
    return {
        'dark': darkfile,
        'light': lightfile,
        'random': lightfile.parent,
    }


def test_wallpaper_new():
    w = Wallpaper.new(
        {
            'dark': 'path/to/dark.jpg',
            'light': 'path/to/light.jgp',
            'random': 'path/to/wallpapers/',
            'cmd': 'nitrogen --save --set-zoom-fill',
        },
        dry_run=True,
    )
    assert w.dry_run
    assert isinstance(w.dark, Path)
    assert isinstance(w.light, Path)
    assert isinstance(w.random, Path)


def test_wallpaper_init(temp_wall_files: dict[str, Path]):
    f = temp_wall_files
    w = Wallpaper(
        dark=f['dark'],
        light=f['light'],
        random=f['random'],
        cmd='nitrogen --save --set-zoom-fill',
        dry_run=True,
    )
    assert w.dry_run


def test_wallpaper_randx(temp_wall: Wallpaper):
    files = [temp_wall.dark, temp_wall.light]
    assert temp_wall.randx() in files


def test_wallpaper_randx_filenotefound(temp_wall: Wallpaper):
    temp_wall.random = Path('file/do/not/exist.jpg')
    with pytest.raises(FileNotFoundError):
        temp_wall.randx()


def test_wallpaper_randx_is_a_file(temp_wall: Wallpaper):
    temp_wall.random = temp_wall.dark
    with pytest.raises(NotADirectoryError):
        temp_wall.randx()


def test_wallpaper_randx_no_files(temp_wall: Wallpaper, tmp_path: Path):
    empty_dir = tmp_path / 'empty_dir'
    empty_dir.mkdir()
    temp_wall.random = empty_dir
    with pytest.raises(FileNotFoundError):
        temp_wall.randx()


def test_wallpaper_get(temp_wall: Wallpaper):
    w = temp_wall
    dark = w.dark
    assert dark == w.get('dark', w.light)
    assert w.light == w.get('light', Path())
    assert w.light == w.get('unknow', w.light)


def test_wallpaper_apply(temp_wall: Wallpaper, temp_file: Callable[..., Path]):
    file = temp_file('tempfile.jpg', 'sometext')
    w = temp_wall
    w.dark = file
    w.set('dark')


def test_wallaper_not_a_file_error(temp_wall: Wallpaper, temp_directory: Callable[..., Path]):
    somedir = temp_directory('somedir')
    with pytest.raises(InvalidFilePathError):
        temp_wall.apply(somedir)


@pytest.mark.parametrize(
    'key, want',
    [
        ('dark', "no 'dark' wallpaper specified."),
        ('light', "no 'light' wallpaper specified."),
        ('random', "no 'random' wallpaper specified."),
        ('cmd', "no 'cmd' wallpaper specified."),
    ],
)
def test_wallpaper_invalid_section(key: str, want: str):
    data = {
        'dark': 'path/to/dark.jpg',
        'light': 'path/to/light.jpg',
        'random': 'path/to/wallpapers',
        'cmd': 'nitrogen --save --set-zoom-fill',
    }
    del data[key]

    w = Wallpaper.new(data, dry_run=True)
    assert w.error.occurred
    assert w.error.mesg == want, f'want: {want!r}, got: {w.error.mesg!r}'
