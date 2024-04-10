# SPDX-FileCopyrightText: 2024-present haaag <git.haaag@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import configparser
import copy
import difflib
import logging
import os
import random
import re
import shlex
import signal
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

__appname__ = 'pythemes'
__version__ = 'v0.0.2'

logger = logging.getLogger(__name__)

# app
ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
HOME = ROOT / __appname__.lower()
APPS: dict[str, App] = {}
THEMES: dict[str, Theme] = {}
HELP = textwrap.dedent(
    f"""{__appname__} {__version__}

options:
    theme           select a theme
    -m, --mode      select a mode [light|dark]
    -l, --list      list available themes
    -d, --diff      show diff
    -c, --confirm   confirm action
    -h, --help      print this help message

locations:
  {HOME}
    """
)

# colors
GREEN = '\033[32m{}\033[0m'
RED = '\033[31m{}\033[0m'
BLUE = '\033[34m{}\033[0m'
ORANGE = '\033[33m{}\033[0m'
CYAN = '\033[36m{}\033[0m'


def log_error_and_exit(msg: str) -> None:
    logger.error(f':{msg}:')
    sys.exit(1)


@dataclass
class App:
    name: str
    file: str
    query: str
    light: str
    dark: str
    cmd: str
    _lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        with self.path.open(mode='r') as f:
            self._lines = f.readlines()

    @property
    def path(self) -> Path:
        return FileManager.get_path(self.file)

    @property
    def lines(self) -> list[str]:
        return self._lines

    def update(self, confirm: bool) -> None:
        if not confirm:
            print('app:', self.name, ORANGE.format('not updated'))
            return

        print('app:', self.name, BLUE.format('updated'))
        with self.path.open(mode='w') as f:
            f.writelines(self.lines)

    def replace(self, index: int, string: str) -> None:
        self._lines[index] = string

    def get_mode(self, mode: str) -> str:
        if mode not in ('light', 'dark'):
            log_error_and_exit(f'invalid mode {mode!r}')
        return self.light if mode == 'light' else self.dark

    def diff(self, idx: int, original_lines: list[str], show: bool) -> None:
        if not show:
            return None
        return diff_this(
            self.name,
            original_lines[idx : idx + 1],
            self.lines[idx : idx + 1],
        )

    @classmethod
    def new(cls, data: dict[str, str]) -> App:
        return cls(
            name=data['name'],
            file=data['file'],
            query=data['query'],
            light=data['light'],
            dark=data['dark'],
            cmd=data['cmd'],
        )


@dataclass
class Wallpaper:
    dark: Path
    light: Path
    random: Path
    cmd: str

    def get_random(self) -> Path:
        files = list(self.random.glob('*.*'))
        return random.choice(files)  # noqa: S311

    def set(self, mode: str, confirm: bool) -> None:
        if not confirm:
            logger.debug('confirming wallpaper not set')
            return

        logger.debug('setting wallpaper')
        img = self.get(mode)
        if not img.is_file():
            img = self.get_random()
            # log_error_and_exit(f'wallpaper file={img!r} not found.')
        logger.debug(f'setting wallpaper={img}')
        Process.run(f'{self.cmd} {img}')

    def get(self, mode: str) -> Path:
        img = self.light if mode == 'light' else self.dark
        logger.debug(f'wallpaper={img}')
        return img

    @classmethod
    def new(cls, data: dict[str, str]) -> Wallpaper:
        return cls(
            dark=FileManager.get_path(data['dark']),
            light=FileManager.get_path(data['light']),
            random=FileManager.get_path(data['random']),
            cmd=data['cmd'],
        )


@dataclass
class Theme:
    name: str
    apps: list[App] = field(default_factory=list)
    wallpaper: Wallpaper = field(init=False)

    def register(self, app: App) -> None:
        self.apps.append(app)

    @staticmethod
    def file(name: str) -> Path | None:
        name = f'{name}.ini'
        files = get_filenames(HOME)
        for file in files:
            if file.name == name:
                return file
        return None

    @staticmethod
    def load(file: Path) -> Theme:
        data = FileManager.read(file)
        if not data:
            msg_err = f'no data found in {file!r}'
            logger.debug(msg_err)
            raise ValueError(msg_err)

        theme = Theme(name=file.stem)
        theme.wallpaper = Wallpaper.new(data.pop('wallpaper'))

        for name, values in data.items():
            values['name'] = name
            app = App.new(values)
            theme.register(app)

        return theme

    @staticmethod
    def get(name: str) -> Theme:
        try:
            theme = THEMES[name]
        except KeyError as _:
            log_error_and_exit(f'theme={name!r} not found')
            sys.exit(1)
        return theme

    def __str__(self) -> str:
        apps = RED.format(f'({len(self.apps)} apps)')
        return f'{BLUE.format(self.name)} theme with {apps}'

    def print(self) -> None:
        print(self)


class FileManager:
    @staticmethod
    def mkdir(path: Path) -> None:
        if path.is_file():
            logger.warn(f'{path=} is a file. aborting...')
            return

        if path.exists():
            logger.debug(f'{path=} already exists')
            return

        logger.info(f'creating {path=}')
        path.mkdir(exist_ok=True)

    @staticmethod
    def read(filepath: Path) -> dict[str, dict[str, str]]:
        if not filepath.exists():
            log_error_and_exit(f'INI file path {filepath.name!r} not found.')

        parser = configparser.ConfigParser()
        parser.read(filepath)

        data = {}

        logger.debug(f'reading {filepath.name!r}')

        try:
            for section in parser.sections():
                if section == 'wallpaper':
                    data[section] = {
                        'light': parser.get(section, 'light'),
                        'dark': parser.get(section, 'dark'),
                        'random': parser.get(section, 'random'),
                        'cmd': parser.get(section, 'cmd'),
                    }
                    continue

                data[section] = {
                    'file': parser.get(section, 'file'),
                    'query': parser.get(section, 'query'),
                    'light': parser.get(section, 'light'),
                    'dark': parser.get(section, 'dark'),
                    'cmd': parser.get(section, 'cmd', fallback=''),
                }
        except configparser.NoOptionError as err:
            msg_err = f'reading {filepath.name!r}: {err}'
            log_error_and_exit(msg_err)
        return data

    @staticmethod
    def get_path(file: str) -> Path:
        return Path(file).expanduser()


class Setup:
    @staticmethod
    def home() -> None:
        FileManager.mkdir(HOME)

    @staticmethod
    def logging(debug: bool = False) -> None:
        level = logging.DEBUG if debug else logging.ERROR
        logging.basicConfig(level=level)

    @staticmethod
    def args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, add_help=False)
        parser.add_argument('theme', nargs='?')
        parser.add_argument('-m', '--mode', type=str)
        parser.add_argument('-l', '--list', action='store_true')
        parser.add_argument('-d', '--diff', action='store_true')
        parser.add_argument('-c', '--confirm', action='store_true')
        parser.add_argument('-v', '--version', action='store_true')
        parser.add_argument('-h', '--help', action='store_true')
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('--test', action='store_true')
        return parser.parse_args()

    def register(self, theme: Theme) -> None:
        THEMES[theme.name] = theme

    def load(self, path: Path, name: str) -> None:
        for file in path.glob('*.ini'):
            data = FileManager.read(file)
            if not data:
                logger.debug(f'no data found in {file!r}')
                continue

            theme = Theme(name=file.stem)
            theme.wallpaper = Wallpaper.new(data.pop('wallpaper'))

            for name, values in data.items():
                values['name'] = name
                app = App.new(values)
                theme.register(app)
            self.register(theme)


class Process:
    @staticmethod
    def get_process_id(name: str) -> list[int]:
        logger.debug(f'getting process ids from program={name!r}')
        command = f'pidof {name}'
        bytes_pidof = subprocess.check_output(shlex.split(command))  # noqa: S603
        pids = bytes_pidof.decode('utf-8').split()
        logger.debug(f'process ids={pids}')
        return [int(p) for p in pids]

    @staticmethod
    def send_signal(pids: list[int], signal: signal.Signals) -> None:
        try:
            for pid in pids:
                logger.debug('sending signal=%s to pid=%s', signal, pid)
                os.kill(pid, signal)
        except OSError as err:
            log_error_and_exit(str(err))

    @staticmethod
    def run(commands: str) -> int:
        logger.debug(f'executing from run: {commands!r}')
        subprocess.run(
            shlex.split(commands),
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,  # noqa: S603
        )
        return 0


class AppManager:
    @staticmethod
    def reload(name: str) -> None:
        process_id = Process.get_process_id(name)
        Process.send_signal(process_id, signal.SIGUSR1)


def find(query: str, list_strings: list[str]) -> tuple[int, str]:
    pattern = re.escape(query).replace('\\{theme\\}', '(\\S+)')
    regex = re.compile(pattern)

    for idx, line in enumerate(list_strings):
        match = regex.search(line)
        if match:
            theme_value = match.group(1)
            return idx, theme_value
    return -1, ''


def get_filenames(path: Path) -> list[Path]:
    return list(path.glob('*.ini'))


def print_menu(options: dict[int, str]) -> None:
    for key in options:
        print(f'{key})', options[key])


def print_version() -> None:
    print(f'{__appname__} {__version__}\n')


def print_list_themes() -> None:
    print_version()
    themes = get_filenames(HOME)
    if not themes:
        print('>', 'no themes found')
        return
    for theme in themes:
        print('>', theme.stem)
    print()


def diff_this(name: str, original: list[str], new: list[str]) -> None:
    diff = list(difflib.unified_diff(original, new, fromfile='original', tofile='new'))

    if not diff:
        print('app:', name, GREEN.format('is up to date.'))
        return

    for line in diff:
        if line.startswith(('---', '+++', '@@')):
            continue
        if line.startswith('+'):
            print(GREEN.format(line), end='')
        elif line.startswith('-'):
            print(RED.format(line), end='')
        else:
            print(line, end='')
    print('-' * 40)


def parse_and_exit(args: argparse.Namespace) -> None:
    if args.help:
        print(HELP)
        sys.exit(0)

    if args.version:
        print_version()
        sys.exit(0)

    if args.list:
        print_list_themes()
        sys.exit(0)

    if not args.theme:
        print(HELP)
        log_error_and_exit('no theme specified')


def main() -> int:
    setup = Setup()
    args = setup.args()
    setup.logging(args.verbose)
    logging.debug(vars(args))

    parse_and_exit(args)

    file = Theme.file(args.theme)
    if not file:
        logger.error(f'theme={args.theme!r} not found')
        return 1

    theme = Theme.load(file)
    theme.print()

    for app in theme.apps:
        idx, current_theme = find(app.query, app.lines)
        if idx == -1:
            logger.debug(f'{app.query=} not found in {app.path.name!r}.')
            continue

        original = app.lines[idx]
        theme_mode = app.get_mode(args.mode)
        next_theme = original.replace(current_theme, theme_mode)
        no_changes = original == next_theme
        if no_changes:
            logger.debug(f'{app.name=} no changes.')
            print('app:', app.name, CYAN.format('no changes.'))
            continue

        app.replace(idx, next_theme)
        app.update(args.confirm)

        app.diff(idx, original_lines=copy.deepcopy(app.lines), show=args.diff)

        if app.cmd and args.confirm:
            Process.run(app.cmd)

    theme.wallpaper.set(args.mode, args.confirm)

    if not args.confirm:
        print(f'\nfor update, use {GREEN.format('--confirm')}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
