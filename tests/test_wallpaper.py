from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from pythemes.__main__ import Wallpaper


@pytest.fixture
def temp_wallpaper_files(temp_directory: Callable[..., Path]) -> dict[str, Path]:
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


@pytest.fixture
def temp_wallpaper(temp_wallpaper_files: dict[str, Path]) -> Wallpaper:
    f = temp_wallpaper_files
    return Wallpaper(
        dark=f['dark'],
        light=f['light'],
        random=f['random'],
        cmd='nitrogen --save --set-zoom-fill',
        dry_run=True,
    )


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
    assert w.has


def test_wallpaper_init(temp_wallpaper_files: dict[str, Path]):
    f = temp_wallpaper_files
    w = Wallpaper(
        dark=f['dark'],
        light=f['light'],
        random=f['random'],
        cmd='nitrogen --save --set-zoom-fill',
        dry_run=True,
    )
    assert w.dry_run
    assert not w.has


def test_wallpaper_randx(temp_wallpaper: Wallpaper):
    files = [temp_wallpaper.dark, temp_wallpaper.light]
    assert temp_wallpaper.randx() in files


def test_wallpaper_get(temp_wallpaper: Wallpaper):
    w = temp_wallpaper
    dark = w.dark
    assert dark == w.get('dark', w.light)
    assert w.light == w.get('light', Path())
    assert w.light == w.get('unknow', w.light)
