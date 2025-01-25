from __future__ import annotations

import argparse
import configparser
import logging
import os
import random
import re
import shlex
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TypeVar

__appname__ = 'pythemes'
__version__ = 'v0.1.3'

logger = logging.getLogger(__name__)

T = TypeVar('T')
INISection = dict[str, str]
INIData = dict[str, INISection]


# app
APP_ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
APP_HOME = APP_ROOT / __appname__.lower()
PROGRAMS_RESTART: list[str] = []
HELP = textwrap.dedent(
    f"""usage: {__appname__} [-h] [-m MODE] [-l] [-a APP] [-L] [-d] [-v] [-t] [--verbose] [theme]

options:
    theme               select a theme
    -m, --mode          select a mode [light|dark]
    -l, --list          list available themes
    -a, --app           apply mode to app
    -L, --list-apps     list available apps in theme
    -d, --dry-run       simulate action
    -h, --help          print this help message

locations:
  {APP_HOME}
    """  # noqa: E501
)

# colors
GREEN = '\033[32m{}'
RED = '\033[31m{}'
BLUE = '\033[34m{}'
YELLOW = '\033[33m{}'
MAGENTA = '\033[35m{}'
CYAN = '\033[36m{}'
GRAY = '\33[37;2m{}'
BOLD = '\033[1m{}'
UNDERLINE = '\033[4m{}'
ITALIC = '\033[3m{}'
END = '\033[0m'


def logerr_exit(msg: str) -> None:
    logger.error(msg)
    sys.exit(1)


@dataclass
class INIFile:
    """
    A dataclass representing an INI file and providing
    methods to read and parse its contents.
    """

    _filepath: Path
    ext: str = 'ini'

    @property
    def filepath(self) -> Path:
        """Returns the path to the INI file as a `Path` object."""
        return Path(self._filepath)

    def parse(self, p: configparser.ConfigParser) -> INIData:
        """
        Parses the contents of a `ConfigParser` object
        into a dictionary-like structure.
        """
        data: INIData = {}
        try:
            for section in p.sections():
                parse_restart(p)
                parse_wallpaper(p, data)
                parse_programs(section, p, data)
        except configparser.NoOptionError as err:
            logerr_exit(f'reading {self.filepath.name!r}: {err}')
        return data

    def read(self) -> configparser.ConfigParser:
        """
        Reads the INI file and returns a `ConfigParser` object containing
        its data.
        """
        if not self.filepath.exists():
            logerr_exit(f'INI file path {self.filepath.name!r} not found.')

        return configparser.ConfigParser()


def parse_restart(p: configparser.ConfigParser) -> None:
    """
    Parses the 'restart' section from a `ConfigParser` object and appends
    the commands to the `PROGRAMS_RESTART` list.
    Removes the 'restart' section after parsing.
    """
    section = 'restart'
    if not p.has_section(section):
        return

    for c in p.get(section, 'cmd').split():
        PROGRAMS_RESTART.append(c)
    p.remove_section(section)


def parse_wallpaper(p: configparser.ConfigParser, data: INIData) -> None:
    """
    Parses the 'wallpaper' section from a `ConfigParser` object and adds
    the wallpaper configuration to the `data` dictionary.
    Removes the 'wallpaper' section after parsing.
    """
    s = 'wallpaper'
    if not p.has_section(s):
        return

    data[s] = {
        'light': p.get(s, 'light'),
        'dark': p.get(s, 'dark'),
        'random': p.get(s, 'random'),
        'cmd': p.get(s, 'cmd'),
    }
    p.remove_section(s)


def parse_programs(
    section: str, p: configparser.ConfigParser, data: INIData
) -> None:
    """
    Parses a program section from a `ConfigParser` object and adds
    the program configuration to the `data` dictionary.
    The section is identified by the `section` argument.
    """
    if not p.has_section(section):
        return

    data[section] = {
        'file': p.get(section, 'file', fallback=''),
        'query': p.get(section, 'query', fallback=''),
        'light': p.get(section, 'light'),
        'dark': p.get(section, 'dark'),
        'cmd': p.get(section, 'cmd', fallback=''),
    }


@dataclass
class ModeAction:
    """
    A dataclass representing an action that can be executed
    based on a mode (light or dark).
    """

    name: str
    light: str
    dark: str
    cmd: str

    def get_mode(self, mode: str) -> str:
        """
        Returns the mode-specific value (light or dark)
        based on the provided mode.
        """
        return self.light if mode == 'light' else self.dark

    def load(self, mode: str) -> None:
        """
        Executes the action based on the specified mode. If in dry-run mode,
        logs the command instead of executing it.
        """
        print(self, end=' ')
        mode = self.get_mode(mode)

        if SysOps.dry_run:
            print(CYAN.format('dry run.') + END)
            logger.debug(f'dry run for command={self.cmd} {mode}')
            return

        SysOps.run(f'{self.cmd} {mode}')
        print(GREEN.format('executed.') + END)

    @classmethod
    def new(cls, data: INISection) -> ModeAction:
        """
        Creates a new ModeAction instance from a dictionary-like INISection
        object.
        """
        del data['file']
        del data['query']
        return cls(**data)

    def __str__(self) -> str:
        return f'{BOLD.format(MAGENTA.format("[cmd]"))}{END} {self.name}'


@dataclass
class Cmd:
    """
    A command dataclass used to wrap commands that can be executed or logged.
    """

    name: str
    cmd: str

    def run(self) -> None:
        """
        Run the command with optional logging.

        If SysOps.dry_run is enabled, logs a dry-run message and returns early.
        Otherwise, logs running and executes the command as usual.
        """

        if not self.cmd:
            return
        print(self, end=' ')

        if SysOps.dry_run:
            print(CYAN.format('dry run.') + END)
            logger.debug(f'dry run for command={self.cmd}')
            return

        logger.debug(f'running command={self.cmd}')
        SysOps.run(self.cmd)
        print(GREEN.format('executed.') + END)

    def __str__(self) -> str:
        return f'{BOLD.format(MAGENTA.format("[cmd]"))}{END} {self.name}'


@dataclass
class Commander:
    """
    A collection of commands to execute or log.
    """

    cmds: list[Cmd] = field(default_factory=list)

    def register(self, cmd: Cmd) -> None:
        """Register a new command to the collection."""
        self.cmds.append(cmd)

    def add(self, a: App) -> None:
        """Add commands from an app if available."""
        if a.has_commands():
            self.register(a.cmd)

    def has_cmds(self) -> bool:
        """Check if there are any commands in the collection."""
        return len(self.cmds) > 0

    def run(self) -> None:
        """Execute all registered commands with logging support."""
        for cmd in self.cmds:
            cmd.run()


class Files:
    """
    A utility class for handling file operations such as reading, writing, and
    manipulating file paths
    """

    dry_run: bool = False

    @staticmethod
    def read_ini(filepath: Path) -> INIData:
        """Reads and parses an INI file into a dictionary-like structure."""
        if not filepath.exists():
            logerr_exit(f'INI file path {filepath.name!r} not found.')

        parser = configparser.ConfigParser()
        parser.read(filepath)

        data: INIData = {}

        logger.debug(f'reading {filepath.name!r}')

        try:
            for section in parser.sections():
                parse_wallpaper(parser, data)
                parse_restart(parser)
                parse_programs(section, parser, data)
        except configparser.NoOptionError as err:
            logerr_exit(f'reading {filepath.name!r}: {err}')

        return data

    @staticmethod
    def readlines(f: Path) -> list[str]:
        """Reads all lines from a file and returns them as a list of strings."""
        if not f.exists():
            logerr_exit(f'file {f.name!r} not found')

        with f.open(mode='r') as file:
            return file.readlines()

    @staticmethod
    def savelines(f: Path, lines: list[str]) -> None:
        """
        Writes a list of strings to a file, with each string representing
        a line.
        """
        with f.open(mode='w') as file:
            file.writelines(lines)

    @staticmethod
    def get_path(file: str) -> Path:
        """
        Expands a file path (including '~' for the home directory) and
        returns it as a Path object.
        """
        return Path(file).expanduser()

    @staticmethod
    def expand_homepaths(command: str) -> str:
        """Expands '~' in a command string to the full home directory path."""
        if not command:
            return ''
        cmds = command.split()
        for i, c in enumerate(cmds):
            if not c.startswith('~'):
                continue
            cmds[i] = Path(c).expanduser().as_posix()
        return ' '.join(cmds)

    @staticmethod
    def mkdir(path: Path) -> None:
        """
        Creates a directory at the specified path if it does not already exist.
        """
        if path.is_file():
            logerr_exit(f'{path=} is a file. aborting...')

        if path.exists():
            logger.debug(f'path={path.as_posix()!r} already exists')
            return

        logger.info(f'creating {path=}')
        path.mkdir(exist_ok=True)


@dataclass
class App:
    """
    A dataclass representing an application with theme-related
    configurations and operations.
    """

    name: str
    file: str
    query: str
    light: str
    dark: str
    cmd: Cmd
    _line_idx: int = -1
    _next_theme: str = ''
    _lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """
        Initializes the instance by reading the lines from the
        configuration file.
        """
        self._lines = Files.readlines(self.path)

    @property
    def path(self) -> Path:
        """Returns the expanded path to the configuration file."""
        return Files.get_path(self.file)

    @property
    def lines(self) -> list[str]:
        """Returns the lines read from the configuration file."""
        return self._lines

    def _read_lines(self) -> None:
        """
        Re-reads the lines from the configuration file and
        updates the `_lines` attribute.
        """
        self._lines = Files.readlines(self.path)

    def update(self) -> None:
        """
        Updates the configuration file with the next theme value
        if changes are detected.
        If in dry-run mode, logs the action without making changes.
        """
        if not self._next_theme:
            logger.error(f'{self.name}: no next theme')
            print(self, RED.format('err not updated.' + END))
            return

        self.replace(self._line_idx, self._next_theme)

        if SysOps.dry_run:
            print(self, CYAN.format('dry run.' + END))
            return

        Files.savelines(self.path, self.lines)

        print(self, BLUE.format('applied.' + END))

    def replace(self, index: int, string: str) -> None:
        """
        Replaces a line in the configuration file at the specified
        index with the given string.
        """
        self._lines[index] = string

    def has_changes(self, m: str) -> bool:
        """
        Checks if there are changes to be applied to the
        configuration file based on the mode.
        """
        self._read_lines()
        idx, current_theme = find(self.query, self.lines)
        if idx == -1:
            logger.warning(
                f'{self.query=} not found in {self.path.as_posix()!r}.'
            )
            return False

        self._line_idx = idx

        original = self.lines[idx]
        theme_mode = self.get_mode(m)

        next_theme = original.replace(current_theme, theme_mode)
        self._next_theme = next_theme

        if current_theme == theme_mode:
            return False

        return original != next_theme

    def has_commands(self) -> bool:
        """Checks if the application has associated commands."""
        return bool(self.cmd)

    def get_mode(self, mode: str) -> str:
        """Returns the theme value for the specified mode."""
        if mode not in ('light', 'dark'):
            logerr_exit(f'invalid mode {mode!r}')
        return self.light if mode == 'light' else self.dark

    @classmethod
    def new(cls, data: INISection) -> App:
        """
        Creates a new App instance from a dictionary-like INISection object.
        """
        name = data['name']
        return cls(
            name=name,
            file=data['file'],
            query=data['query'],
            light=data['light'],
            dark=data['dark'],
            cmd=Cmd(name, Files.expand_homepaths(data['cmd'])),
        )

    def __str__(self) -> str:
        return f'{BOLD.format(YELLOW.format("[app]"))}{END} {self.name}'


@dataclass
class Wallpaper:
    """
    A dataclass representing wallpaper settings and operations
    for light, dark, and random modes.
    """

    dark: Path
    light: Path
    random: Path
    cmd: str

    def randx(self) -> Path:
        """Randomly selects a wallpaper."""
        files = list(self.random.glob('*.*'))
        return random.choice(files)  # noqa: S311

    def set(self, mode: str) -> None:
        """
        Sets the wallpaper based on the specified mode.
        If the mode is not explicitly light or dark, a random
        wallpaper is selected.
        """
        self.apply(self.get(mode, self.randx()))

    def apply(self, path: Path) -> None:
        """
        Applies the wallpaper at the specified path. If in dry-run mode,
        logs the action without making changes.
        """
        if not path.is_file():
            logger.debug(f'wallpaper={path} is not a file')
            return

        print(self, path.name, end=' ')

        if SysOps.dry_run:
            print(CYAN.format('dry run.' + END))
            logger.debug(f'dry run for wallpaper={path}')
            return

        logger.debug(f'setting wallpaper={path!s}')
        SysOps.run(f'{self.cmd} {path}')

        print(BLUE.format('setted.' + END))

    def get(self, mode: str, default: Path) -> Path:
        """
        Retrieves the wallpaper path for the specified mode.
        If no wallpaper is set for the mode, returns the default path.
        """
        img = self.light if mode == 'light' else self.dark
        logger.debug(f'wallpaper={img}')
        if not img:
            return default
        return img

    def __str__(self) -> str:
        return f'{BOLD.format(GREEN.format("[wal]"))}{END}'

    @classmethod
    def new(cls, data: INISection) -> Wallpaper:
        """
        Creates a new Wallpaper instance from a dictionary-like INISection.
        """
        return cls(
            dark=Files.get_path(data['dark']),
            light=Files.get_path(data['light']),
            random=Files.get_path(data['random']),
            cmd=data['cmd'],
        )


@dataclass
class Theme:
    """
    A dataclass representing a theme, including its associated apps, commands,
    and wallpaper settings.
    """

    name: str
    apps: dict[str, App] = field(default_factory=dict)
    cmds: list[ModeAction] = field(default_factory=list)
    dry_run: bool = False
    wallpaper: Wallpaper = field(init=False)
    updates: int = 0

    def register_app(self, app: App) -> None:
        """Registers an app with the theme if it is not already registered."""
        if not self.apps.get(app.name):
            self.apps[app.name] = app

    def register_cmd(self, cmd: ModeAction) -> None:
        """Registers a command."""
        self.cmds.append(cmd)

    @property
    def has_updates(self) -> bool:
        """Checks if the theme has any updates."""
        return self.updates > 0

    @staticmethod
    def file(name: str) -> Path | None:
        """
        Searches for a theme file by name in the application home directory.
        """
        name = f'{name}.ini'
        files = get_filenames(APP_HOME)
        for file in files:
            if file.name == name:
                return file
        return None

    @staticmethod
    def load(file: Path) -> Theme:
        """
        Loads a theme from a file and initializes its apps, commands, and
        wallpaper settings.
        """
        data = Files.read_ini(file)
        if not data:
            msg_err = f'no data found in {file!r}'
            logger.debug(msg_err)
            raise ValueError(msg_err)

        theme = Theme(name=file.stem)
        theme.wallpaper = Wallpaper.new(data.pop('wallpaper'))

        for name, values in data.items():
            values['name'] = name

            if not values.get('file') and not values.get('query'):
                cmd = ModeAction.new(values)
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
    def get(s: str) -> Theme:
        """Retrieves a theme by name from the application home directory."""
        filename = Theme.file(s)
        if not filename:
            logger.error(f'theme={s!r} not found')
            sys.exit(1)

        return Theme.load(filename)

    def __str__(self) -> str:
        apps = RED.format(f'({len(self.apps)} apps)')
        s = f'{BLUE.format(self.name)}{END} theme with {apps}'
        return f'{BOLD.format(UNDERLINE.format(s))}{END}'

    def print(self) -> None:
        print(f'> {self}', end='\n\n')


class SysOps:
    """
    A utility class for system operations such as process management,
    signal handling, and command execution.
    """

    dry_run: bool = False

    @staticmethod
    def pid(name: str) -> list[int]:
        """Retrieves the process IDs (PIDs) of a running program by its name."""
        command = f'pidof {name}'
        bytes_pidof = subprocess.check_output(shlex.split(command))  # noqa: S603
        pids = bytes_pidof.decode('utf-8').split()
        logger.debug(f'program={name!r} with {pids=}')
        return [int(p) for p in pids]

    @staticmethod
    def send_signal(pids: list[int], signal: signal.Signals) -> None:
        """Sends a signal to a list of process IDs (PIDs)."""
        try:
            for pid in pids:
                logger.debug('sending signal=%s to pid=%s', signal, pid)
                os.kill(pid, signal)
        except OSError as err:
            logerr_exit(str(err))

    @staticmethod
    def run(commands: str) -> int:
        """Executes a shell command and returns its exit code."""
        logger.debug(f'executing from run: {commands!r}')
        try:
            proc = subprocess.run(  # noqa: S603
                shlex.split(commands),
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            err_msg = f"'{commands}': " + str(exc)
            print(RED.format('[err] ') + err_msg + END)
            return 1
        return proc.returncode

    @staticmethod
    def restart(s: str) -> None:
        """
        Restarts a program by sending a `SIGUSR1` signal to its process IDs.
        If in dry-run mode, logs the action without sending the signal.
        """
        print(BOLD.format(BLUE.format('[sys]')) + END, s, end=' ')
        pids = SysOps.pid(s)

        if SysOps.dry_run:
            logger.debug(f'dry run for reloading app={s} with {pids=}')
            print(CYAN.format('dry run.') + END)
            return None

        print(CYAN.format('restarted.') + END)
        return SysOps.send_signal(pids, signal.SIGUSR1)

    @staticmethod
    def is_executable(c: str) -> bool:
        """
        Checks if a command is executable by verifying its
        existence in the system's PATH.
        """
        return SysOps.run(f'which {c}') == 0


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
    """Returns a list of all files in a directory with the extension .ini"""
    return list(path.glob('*.ini'))


def print_list_themes() -> None:
    """Prints a list of all themes in the themes directory."""
    themes = get_filenames(APP_HOME)
    if not themes:
        print('> no themes found')
        return

    for t in themes:
        print(BOLD.format(BLUE.format('[theme]')) + END, t.stem)


def print_list_apps(t: str | None) -> int:
    """Prints a list of all apps for a given theme."""
    if not t:
        logger.error('no theme specified')
        return 1

    file = Theme.file(t)
    if not file:
        logger.error(f'theme={t} not found')
        return 1

    themes = Theme.load(file)
    n = RED.format(f'({len(themes.apps)} apps)')
    print(f'{BLUE.format(t)}{END} theme with {n}\n')

    for app in themes.apps.values():
        print(app)

    return 0


def get_app(t: str | None, s: str) -> App | None:
    """Returns an App object for a given theme and app name."""
    if not t:
        logger.error('no theme specified')
        return None

    file = Theme.file(t)
    if not file:
        logger.error(f"theme='{t}' not found")
        return None

    themes = Theme.load(file)
    app = themes.apps.get(s)
    if not app:
        logger.error(f"app='{s}' not found")
        return None

    return app


def parse_and_exit(args: argparse.Namespace) -> None:
    """Parses command-line arguments and performs corresponding actions."""
    if args.help:
        print(HELP)
        sys.exit(0)

    if args.app:
        app = get_app(args.theme, args.app)
        if not app:
            sys.exit(1)
        process_app(app, args.mode)
        sys.exit(0)

    if args.version:
        print(f'{__appname__} {__version__}\n')
        sys.exit(0)

    if args.test:
        print('testing mode...')
        sys.exit(0)

    if args.list:
        print_list_themes()
        sys.exit(0)

    if args.list_apps:
        print_list_apps(args.theme)
        sys.exit(0)

    if not args.theme:
        print(HELP)
        logerr_exit('no theme specified')


def process_theme(theme: str) -> Theme:
    """Process a theme and return a Theme object."""
    filename = Theme.file(theme)
    if not filename:
        logger.error(f'theme={theme!r} not found')
        print()
        print_list_themes()
        sys.exit(1)

    return Theme.load(filename)


def process_app(app: App, mode: str | None) -> None:
    """Process an app and update it if needed."""
    if not mode:
        logger.error('no mode specified (dark|light)')
        return
    if not app.has_changes(mode):
        print(app, ITALIC.format(GRAY.format('no changes needed.')) + END)
        return
    app.update()


class Setup:
    """
    A utility class for initial setup tasks such as argument parsing, logging
    configuration, and directory creation.
    """

    @staticmethod
    def init(path: Path) -> argparse.Namespace:
        """Initializes the application setup."""
        args = Setup.args()
        Setup.logging(args.verbose)
        Files.mkdir(path)
        logging.debug(vars(args))
        parse_and_exit(args)

        SysOps.dry_run = args.dry_run

        return args

    @staticmethod
    def logging(debug: bool = False) -> None:
        """
        Configures the logging format and level based on the debug flag.
        """
        logging_format = (
            '[{levelname:^7}] {name:<30}: {message} (line:{lineno})'
        )
        level = logging.DEBUG if debug else logging.ERROR
        logging.basicConfig(
            level=level,
            format=logging_format,
            style='{',
            handlers=[logging.StreamHandler()],
        )

    @staticmethod
    def args() -> argparse.Namespace:
        """
        Parses and returns command-line arguments.
        """
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False,
        )
        parser.add_argument('theme', nargs='?')
        parser.add_argument('-m', '--mode', type=str)
        parser.add_argument('-l', '--list', action='store_true')
        parser.add_argument('-a', '--app', type=str)
        parser.add_argument('-L', '--list-apps', action='store_true')
        parser.add_argument('-d', '--dry-run', action='store_true')
        parser.add_argument('-v', '--version', action='store_true')
        parser.add_argument('-h', '--help', action='store_true')
        parser.add_argument('-t', '--test', action='store_true')
        parser.add_argument('--verbose', action='store_true')
        return parser.parse_args()


def main() -> int:
    args = Setup.init(APP_HOME)
    theme = process_theme(args.theme)
    theme.print()

    mode = args.mode
    c = Commander()

    for app in theme.apps.values():
        process_app(app, mode)
        # commands apps
        c.add(app)

        time.sleep(0.010)
        theme.updates += 1

    if theme.has_updates:
        # run commands
        for cmd in theme.cmds:
            cmd.load(mode)

        if c.has_cmds():
            c.run()

        theme.wallpaper.set(mode)

        # reload programs
        for p in PROGRAMS_RESTART:
            SysOps.restart(p)

        print(
            f'\n> {BOLD.format(BLUE.format(theme.updates)) + END} apps updated'
        )
    else:
        print('\n> no apps updated')

    return 0


if __name__ == '__main__':
    sys.exit(main())
