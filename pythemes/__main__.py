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
__version__ = 'v0.1.0'

logger = logging.getLogger(__name__)

# TODO:
# - [X] Expand `~` in commands
# - [ ] On `diff` shows `not updated` and `is up to date`

# app
APP_ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
APP_HOME = APP_ROOT / __appname__.lower()
APPS: dict[str, App] = {}
THEMES: dict[str, Theme] = {}
HELP = textwrap.dedent(
    f"""usage: {__appname__} [-h] [-m MODE] [-l] [-d] [-c] [-v] [--verbose] [theme]

options:
    theme           select a theme
    -m, --mode      select a mode [light|dark]
    -l, --list      list available themes
    -d, --diff      show diff
    -c, --confirm   confirm action
    -h, --help      print this help message

locations:
  {APP_HOME}
    """
)

# colors
GREEN = '\033[32m{}\033[0m'
RED = '\033[31m{}\033[0m'
BLUE = '\033[34m{}\033[0m'
YELLOW = '\033[33m{}\033[0m'
MAGENTA = '\033[35m{}\033[0m'
CYAN = '\033[36m{}\033[0m'


def log_error_and_exit(msg: str) -> None:
    logger.error(f':{msg}:')
    sys.exit(1)


def expand_homepaths(command: str) -> str:
    """Parse home paths in a command string"""
    if not command:
        return ''
    cmds = command.split()
    for i, c in enumerate(cmds):
        if not c.startswith('~'):
            continue
        cmds[i] = Path(c).expanduser().as_posix()
    return ' '.join(cmds)


@dataclass
class Command:
    name: str
    light: str
    dark: str
    cmd: str

    def get_mode(self, mode: str) -> str:
        return self.light if mode == 'light' else self.dark

    def load(self, mode: str, confirm: bool = False) -> None:
        print(self, end=' ')
        mode = self.get_mode(mode)
        if not confirm:
            print(YELLOW.format('not executed'))
            return

        Process.run(f'{self.cmd} {mode}')
        print(GREEN.format('executed'))

    @classmethod
    def new(cls, data: dict[str, str]) -> Command:
        del data['file']
        del data['query']
        return cls(**data)

    def __str__(self) -> str:
        return f'{MAGENTA.format("[cmd]")} {self.name}'


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
            # print(self, YELLOW.format('not updated'))
            return

        print(self, BLUE.format('updated'))
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
            self,
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
            cmd=expand_homepaths(data['cmd']),
        )

    def __str__(self) -> str:
        return f'{YELLOW.format('[app]')} {self.name}'


@dataclass
class Wallpaper:
    dark: Path
    light: Path
    random: Path
    cmd: str

    def randx(self) -> Path:
        files = list(self.random.glob('*.*'))
        return random.choice(files)  # noqa: S311

    def apply(self, mode: str, confirm: bool) -> None:
        if not confirm:
            logger.debug('wallpaper not set, use --confirm')
            return

        logger.debug('setting wallpaper')
        img = self.get(mode)
        if not img.is_file():
            logger.debug(f'wallpaper={img} is not a file, using random')
            img = self.randx()
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
    cmds: list[Command] = field(default_factory=list)
    wallpaper: Wallpaper = field(init=False)

    def register_app(self, app: App) -> None:
        self.apps.append(app)

    def register_cmd(self, cmd: Command) -> None:
        self.cmds.append(cmd)

    @staticmethod
    def file(name: str) -> Path | None:
        name = f'{name}.ini'
        files = get_filenames(APP_HOME)
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

            if not values.get('file') and not values.get('query'):
                cmd = Command.new(values)
                theme.register_cmd(cmd)
                continue

            f = values.get('file')
            if f is None:
                continue

            filepath = Path(f).expanduser()

            if not filepath.exists():
                logger.warn(f'filepath: {filepath!s} do not exists.')
                continue

            app = App.new(values)
            theme.register_app(app)

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
        print(self, end='\n\n')


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
                    'file': parser.get(section, 'file', fallback=''),
                    'query': parser.get(section, 'query', fallback=''),
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
        FileManager.mkdir(APP_HOME)

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


class Process:
    @staticmethod
    def pid(name: str) -> list[int]:
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
        try:
            proc = subprocess.run(
                shlex.split(commands),
                # stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            err_msg = f"'{commands}': " + str(exc)
            print(RED.format('[err] ') + err_msg)
            return 1
        return proc.returncode


class AppManager:
    @staticmethod
    def reload(name: str) -> None:
        process_id = Process.pid(name)
        Process.send_signal(process_id, signal.SIGUSR1)


def find(query: str, list_strings: list[str]) -> tuple[int, str]:
    """Finds the first match of a query in a list of strings and
    returns the index and extracted theme value.
    """
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


def print_version() -> None:
    print(f'{__appname__} {__version__}\n')


def print_list_themes() -> None:
    print_version()
    themes = get_filenames(APP_HOME)
    if not themes:
        print('>', 'no themes found')
        return
    for theme in themes:
        print('>', theme.stem)
    print()


def diff_this(app: App, original: list[str], new: list[str]) -> None:
    diff = list(difflib.unified_diff(original, new, fromfile='original', tofile='new'))

    if not diff:
        print(app, GREEN.format('is up to date.'))
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


def restart_dwm() -> None:
    Process.send_signal(Process.pid('dwm'), signal.SIGUSR1)


def restart_st() -> None:
    Process.send_signal(Process.pid('st'), signal.SIGUSR1)


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
            print(app, CYAN.format('no changes.'))
            continue

        app.replace(idx, next_theme)
        app.update(args.confirm)

        app.diff(idx, original_lines=copy.deepcopy(app.lines), show=args.diff)

        if app.cmd and args.confirm:
            Process.run(app.cmd)

    theme.wallpaper.apply(args.mode, args.confirm)

    for cmd in theme.cmds:
        cmd.load(args.mode, args.confirm)

    if not args.confirm:
        print(f'\nfor update, use {GREEN.format('--confirm')}')

    if args.confirm:
        restart_dwm()
        restart_st()
    return 0


if __name__ == '__main__':
    sys.exit(main())
