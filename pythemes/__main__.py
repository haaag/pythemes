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
from typing import Self

__appname__ = 'pythemes'
__version__ = 'v0.1.4'

logger = logging.getLogger(__name__)

INISection = dict[str, str]
INIData = dict[str, INISection]


# app
APP_ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
APP_HOME = APP_ROOT / __appname__.lower()
PROGRAMS_RESTART: list[str] = []
HELP = textwrap.dedent(
    f"""usage: {__appname__} [-h] [-m MODE] [-l] [-a APP] [-L] [-d] [-v] [-c COLOR] [--verbose] [theme]

options:
    theme               Theme name
    -m, --mode          Select a mode [light|dark]
    -l, --list          List available themes
    -a, --app           Apply mode to app
    -L, --list-apps     List available apps in theme
    -d, --dry-run       Do not make any changes
    -V, --version       Print version and exit
    -v, --verbose       Increase output verbosity
    -c, --color         Enable color [always|never] (default: always)
    -h, --help          Print this help message

locations:
  {APP_HOME}"""  # noqa: E501
)

# colors
BLUE = '\033[34m'
CYAN = '\033[36m'
GRAY = '\33[37m'
GREEN = '\033[32m'
MAGENTA = '\033[35m'
RED = '\033[31m'
YELLOW = '\033[33m'
END = '\033[0m'
# styles
BOLD = '\033[1m'
ITALIC = '\033[3m'
UNDERLINE = '\033[4m'


@dataclass
class INIFile:
    """
    A dataclass representing an INI file and providing
    methods to read and parse its contents.
    """

    path: Path
    _data: INIData = field(default_factory=dict)
    _config: configparser.ConfigParser = field(default_factory=configparser.ConfigParser)

    def __post_init__(self):
        if not self.path.exists():
            err_msg = f'INI file path {self.path.name!r} not found.'
            raise FileNotFoundError(err_msg)

    @property
    def filepath(self) -> Path:
        """Returns the path to the INI file as a `Path` object."""
        return Path(self.path)

    @property
    def data(self) -> INIData:
        """Returns the parsed data from the INI file."""
        return self._data

    @property
    def config(self) -> configparser.ConfigParser:
        """Returns the `ConfigParser` object used to read the INI file."""
        return self._config

    def parse(self) -> Self:
        """
        Parses the contents of a `ConfigParser` object into a dictionary-like structure.
        """
        for section in self.config.sections():
            try:
                parse_restart(self.config)
                parse_wallpaper(self.config, self._data)
                parse_raw_program(section, self.config, self._data)
            except configparser.NoOptionError as err:
                logger.warning(f'reading {self.filepath.name!r}: {err}')
                continue

        return self

    def read(self) -> Self:
        """
        Reads the INI file and populates the config attribute with its data.
        """
        if not self.filepath.exists():
            err_msg = f'INI file path {self.filepath.name!r} not found.'
            raise FileNotFoundError(err_msg)

        self._config.read(self.filepath, encoding='utf-8')
        if not self.config.sections():
            errmsg = f'No sections found in {self.filepath.name!r}.'
            raise configparser.NoSectionError(errmsg)
        return self

    def get(self, section: str) -> INISection | None:
        """Returns the section of the INI file with the given name."""
        if not self.config.has_section(section):
            return None
        return dict(self.config[section])

    def add(self, section_name: str, data: INISection) -> Self:
        """Adds a new section to the config data."""
        self._config.add_section(section_name)
        for key, value in data.items():
            self._config.set(section_name, key, value)
        return self


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


def parse_raw_program(section: str, p: configparser.ConfigParser, data: INIData) -> None:
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
        'light': p.get(section, 'light', fallback=''),
        'dark': p.get(section, 'dark', fallback=''),
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
    dry_run: bool

    def get_mode(self, mode: str) -> str:
        """
        Returns the mode-specific value (light or dark)
        based on the provided mode.
        """
        match mode:
            case 'light':
                return self.light
            case 'dark':
                return self.dark
            case _:
                err_msg = f'invalid mode {mode!r}'
                raise ValueError(err_msg)

    def load(self, mode: str) -> None:
        """
        Executes the action based on the specified mode. If in dry-run mode,
        logs the command instead of executing it.
        """
        print(self, end=' ')
        mode = self.get_mode(mode)

        if self.dry_run:
            print(colorize('dry run', ITALIC, CYAN))
            logger.debug(f'dry run for command={self.cmd} {mode}')
            return

        SysOps.run(f'{self.cmd} {mode}')
        print(colorize('executed', ITALIC, GREEN))

    @classmethod
    def new(cls, data: INISection, dry_run: bool) -> ModeAction:
        """
        Creates a new ModeAction instance from a dictionary-like INISection
        object.
        """
        return cls(
            name=data['name'],
            light=data['light'],
            dark=data['dark'],
            cmd=data['cmd'],
            dry_run=dry_run,
        )

    def __str__(self) -> str:
        return f'{colorize("[cmd]", BOLD, MAGENTA)} {self.name}'


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
            print(colorize('dry run', ITALIC, CYAN))
            logger.debug(f'dry run for command={self.cmd}')
            return

        logger.debug(f'running command={self.cmd}')
        SysOps.run(self.cmd)
        print(colorize('executed', ITALIC, GREEN))

    def __str__(self) -> str:
        return f'{colorize("[cmd]", BOLD, MAGENTA)} {self.name}'


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

    @staticmethod
    def readlines(f: Path) -> list[str]:
        """Reads all lines from a file and returns them as a list of strings."""
        if not f.exists():
            err_msg = f"file '{f}' does not exist."
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

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
    def get_path(f: str) -> Path:
        """
        Expands a file path (including '~' for the home directory) and
        returns it as a Path object.
        """
        return Path(f).expanduser()

    @staticmethod
    def expand_homepaths(command: str) -> str:
        """Expands '~' in a command string to the full home directory path."""
        if '~' not in command:
            return command
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
            err_msg = f'Cannot create directory: {path!s} is a file.'
            raise IsADirectoryError(err_msg)
        if path.exists():
            logger.debug(f'path={path!s} already exists')
            return

        logger.info(f'creating {path=}')
        path.mkdir(exist_ok=True)


class AppError:
    """Represents an error in an application."""

    mesg: str = ''
    occurred: bool = False


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
    dry_run: bool
    error: AppError = field(default_factory=AppError)
    _line_idx: int = -1
    _next_theme: str = ''
    _lines: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        """Returns the expanded path to the configuration file."""
        return Files.get_path(self.file)

    @property
    def lines(self) -> list[str]:
        """Returns the lines read from the configuration file."""
        return self._lines

    def read_lines(self) -> None:
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
            print(self, colorize('err not updated', ITALIC, RED))
            return

        self.replace(self._line_idx, self._next_theme)

        if self.dry_run:
            print(self, colorize('dry run', ITALIC, CYAN))
            return

        Files.savelines(self.path, self.lines)

        print(self, colorize('applied', ITALIC, BLUE))

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
        self.read_lines()
        idx, current_theme = find(self.query, self.lines)
        if idx == -1:
            logger.warning(f'{self.name}: {self.query=} not found in {self.path.as_posix()!r}.')
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
            logger.error(f'invalid mode {mode!r}')
            sys.exit(1)
        return self.light if mode == 'light' else self.dark

    def validate(self) -> None:
        """Validates the application."""
        if not self.file:
            self.error.mesg = f'{self.name}: no file specified.'
            self.error.occurred = True
        if not self.dark:
            self.error.mesg = f'{self.name}: no dark theme specified.'
            self.error.occurred = True
        if not self.light:
            self.error.mesg = f'{self.name}: no light theme specified.'
            self.error.occurred = True
        if '{theme}' not in self.query:
            self.error.mesg = f"{self.name}: query does not contain placeholder '{{theme}}'."
            self.error.occurred = True
        if not self.query:
            self.error.mesg = f'{self.name}: no query specified.'
            self.error.occurred = True
        if not self.path.exists():
            self.error.mesg = f"{self.name}: filepath '{self.path!s}' do not exists."
            self.error.occurred = True

    @classmethod
    def new(cls, data: INISection, dry_run: bool) -> App:
        """
        Creates a new App instance from a dictionary-like INISection object.
        """
        name = data['name']
        return cls(
            name=name,
            file=data.get('file', ''),
            query=data.get('query', ''),
            light=data.get('light', ''),
            dark=data.get('dark', ''),
            cmd=Cmd(name, Files.expand_homepaths(data.get('cmd', ''))),
            dry_run=dry_run,
        )

    def __str__(self) -> str:
        c = YELLOW
        if self.error.occurred:
            c = RED
        return f'{colorize("[app]", BOLD, c)} {self.name}'


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
    dry_run: bool
    has: bool = False

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

        if self.dry_run:
            print(colorize('dry run', ITALIC, CYAN))
            logger.debug(f'dry run for wallpaper={path}')
            return

        logger.debug(f'setting wallpaper={path!s}')
        SysOps.run(f'{self.cmd} {path}')

        print(colorize('set', ITALIC, BLUE))

    def get(self, mode: str, fallback: Path) -> Path:
        """
        Retrieves the wallpaper path for the specified mode.
        If no wallpaper is set for the mode, returns the default path.
        """
        img: Path
        match mode:
            case 'light':
                img = self.light
            case 'dark':
                img = self.dark
            case _:
                img = fallback
        logger.debug(f'wallpaper={img}')
        return img

    @classmethod
    def new(cls, data: INISection, dry_run: bool) -> Wallpaper:
        """
        Creates a new Wallpaper instance from a dictionary-like INISection.
        """
        return cls(
            dark=Files.get_path(data['dark']),
            light=Files.get_path(data['light']),
            random=Files.get_path(data['random']),
            cmd=data['cmd'],
            dry_run=dry_run,
            has=True,
        )

    def __str__(self) -> str:
        return colorize('[wal]', BOLD, GREEN)


@dataclass
class Theme:
    """
    A dataclass representing a theme, including its associated apps, commands,
    and wallpaper settings.
    """

    name: str
    inifile: INIFile
    dry_run: bool
    apps: dict[str, App] = field(default_factory=dict)
    cmds: list[ModeAction] = field(default_factory=list)
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

    def parse_apps(self) -> None:
        self.inifile.read().parse()
        if not self.inifile.data:
            msg_err = f'no data found in {self.inifile.filepath!r}'
            logger.debug(msg_err)
            raise ValueError(msg_err)

        if self.inifile.data.get('wallpaper', False):
            self.wallpaper = Wallpaper.new(
                self.inifile.data.pop('wallpaper'),
                dry_run=self.dry_run,
            )

        for name, values in self.inifile.data.items():
            values['name'] = name

            if not values.get('file') and not values.get('query'):
                cmd = ModeAction.new(values, dry_run=self.dry_run)
                self.register_cmd(cmd)
                continue

            f = values.get('file')
            if f is None:
                continue

            app = App.new(values, dry_run=self.dry_run)
            app.validate()
            self.register_app(app)

    def get(self, appname: str) -> App | None:
        """Retrieves an app by its name."""
        section = self.inifile.get(appname)
        if not section:
            return None
        section['name'] = appname
        app = App.new(section, dry_run=self.dry_run)
        app.validate()
        return app

    def errors(self) -> int:
        """Returns the total number of errors in the theme."""
        return sum(app.error.occurred for app in self.apps.values())

    def print(self) -> None:
        print(f'> {self}', end='\n\n')

    def __str__(self) -> str:
        apps = colorize(f'({len(self.apps)} apps)', RED)
        return f'{colorize(self.name, UNDERLINE, BOLD, BLUE)} theme {apps}'


class SysOps:
    """
    A utility class for system operations such as process management,
    signal handling, and command execution.
    """

    dry_run: bool = False
    color: bool = False

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
            raise err

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
            print(colorize('[err]', BOLD, RED), err_msg)
            return 1
        return proc.returncode

    @staticmethod
    def restart(s: str) -> None:
        """
        Restarts a program by sending a `SIGUSR1` signal to its process IDs.
        If in dry-run mode, logs the action without sending the signal.
        """
        print(colorize('[sys]', BOLD, BLUE), s, end=' ')
        pids = SysOps.pid(s)

        if SysOps.dry_run:
            logger.debug(f'dry run for reloading app={s} with {pids=}')
            print(colorize('dry run', ITALIC, CYAN))
            return None

        print(colorize('restarted', ITALIC, CYAN))
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
    if len(list_strings) == 0:
        logger.warning('list of strings is empty.')
        return -1, ''

    if not query:
        logger.warning('query is empty.')
        return -1, ''

    if '{theme}' not in query:
        logger.warning('query does not contain placeholder {theme}.')
        return -1, ''

    pattern = re.escape(query).replace('\\{theme\\}', '(\\S+)')
    regex = re.compile(pattern)

    for idx, line in enumerate(list_strings):
        match = regex.search(line)
        if match:
            theme_value = match.group(1)
            return idx, theme_value
    return -1, ''


def version() -> None:
    print(f'{__appname__} {__version__}')


def logme(s: str) -> None:
    print(f'{__appname__} {__version__}: {s}')


def get_filenames(path: Path) -> list[Path]:
    """Returns a list of all files in a directory with the extension .ini"""
    return list(path.glob('*.ini'))


def print_list_themes() -> None:
    """Prints a list of all themes in the themes directory."""
    themes_files = get_filenames(APP_HOME)
    if not themes_files:
        print('> no themes found')
        return

    max_len = max(len(t.stem) for t in themes_files)
    for fn in themes_files:
        ini = INIFile(fn)
        theme = Theme(fn.stem, ini, dry_run=True)
        theme.parse_apps()
        apps = colorize(f'({len(theme.apps)} apps)', ITALIC, GRAY)
        t = colorize('[theme]', BOLD, BLUE)
        print(f'{t} {theme.name:<{max_len}} {apps}')


def print_list_apps(t: str | None) -> int:
    """Prints a list of all apps for a given theme."""
    if not t:
        logger.error('no theme specified')
        return 1

    fn = get_filetheme(t)
    if not fn:
        logger.error(f'theme={t} not found')
        return 1

    inifile = INIFile(fn)
    theme = Theme(t, inifile, dry_run=SysOps.dry_run)
    theme.parse_apps()
    theme.print()

    for app in theme.apps.values():
        print(app)

    return 0


def get_app(t: str | None, appname: str) -> App | None:
    """Returns an App object for a given theme and app name."""
    if not t:
        logger.error('no theme specified')
        return None

    fn = get_filetheme(t)
    if not fn:
        logger.error(f"theme='{t}' not found")
        return None

    ini = INIFile(fn).read().parse()
    theme = Theme(t, ini, dry_run=SysOps.dry_run)
    app = theme.get(appname)
    if not app:
        logger.error(f"app='{appname}' not found")
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
        version()
        sys.exit(0)
    if args.test:
        print('testing mode...')
        sys.exit(0)
    if args.list:
        version()
        print('\nThemes found:')
        print_list_themes()
        sys.exit(0)
    if args.list_apps:
        print_list_apps(args.theme)
        sys.exit(0)
    if not args.theme:
        print(HELP)
        sys.exit(0)


def process_app(app: App, mode: str | None) -> None:
    """Process an app and update it if needed."""
    if not mode:
        logme('no mode specified (dark|light)')
        sys.exit(1)
        return
    if app.error.occurred:
        logger.warning(app.error.mesg)
        print(app, colorize('err', ITALIC, RED))
        return
    if app.dry_run:
        print(app, colorize('dry run', ITALIC, CYAN))
        return
    if not app.has_changes(mode):
        print(app, colorize('no changes', ITALIC, GRAY))
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
        # globals
        SysOps.dry_run = args.dry_run
        SysOps.color = args.color == 'always'

        logging.debug(vars(args))
        parse_and_exit(args)
        return args

    @staticmethod
    def logging(verbose: int) -> None:
        """
        Configures the logging format and level based on the debug flag.
        """
        logging_format = '[{levelname:^7}] {name:<30}: {message} (line:{lineno})'
        levels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
        level = levels[min(verbose, len(levels) - 1)]
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
        parser.add_argument('-m', '--mode', type=str, choices=['dark', 'light'])
        parser.add_argument('-l', '--list', action='store_true')
        parser.add_argument('-a', '--app', type=str)
        parser.add_argument('-c', '--color', type=str, choices=['always', 'never'], default='always')  # noqa: E501
        parser.add_argument('-L', '--list-apps', action='store_true')
        parser.add_argument('-d', '--dry-run', action='store_true')
        parser.add_argument('-V', '--version', action='store_true')
        parser.add_argument('-h', '--help', action='store_true')
        parser.add_argument('-t', '--test', action='store_true')
        parser.add_argument('-v', '--verbose', action='count', default=0)
        return parser.parse_args()


def get_filetheme(name: str) -> Path | None:
    themes = get_filenames(APP_HOME)
    for t in themes:
        if t.stem == name:
            return t
    return None


def colorize(text: str, *styles: str) -> str:
    """Returns the given text with the specified styles applied."""
    # https://no-color.org/
    if os.getenv('NO_COLOR'):
        return text
    if not styles or not SysOps.color:
        return text
    return ''.join(styles) + text + END


def handle_missing_theme(theme_name: str) -> int:
    """Handles the case when a theme is not found."""
    logme(f'theme={theme_name!r} not found')
    print('\nThemes found:')
    print_list_themes()
    return 1


def initialize_theme(theme_name: str, filepath: Path, dry_run: bool) -> Theme:
    """Initializes and parses the theme from the INI file."""
    ini = INIFile(filepath)
    theme = Theme(theme_name, ini, dry_run=dry_run)
    theme.parse_apps()
    theme.print()
    return theme


def process_theme(theme: Theme, mode: str) -> None:
    """Processes theme apps, executes commands, and handles updates."""
    commander = Commander()

    for app in theme.apps.values():
        process_app(app, mode)
        if app.error.occurred:
            continue
        commander.add(app)
        time.sleep(0.005)
        theme.updates += 1

    handle_theme_updates(theme, commander, mode)


def handle_theme_updates(theme: Theme, commander: Commander, mode: str) -> None:
    """Handles updates, executes commands, and restarts necessary programs."""
    if not theme.has_updates:
        print('\n> no apps updated')
        return

    for cmd in theme.cmds:
        cmd.load(mode)

    if commander.has_cmds():
        commander.run()

    if theme.wallpaper.has:
        theme.wallpaper.set(mode)

    for program in PROGRAMS_RESTART:
        SysOps.restart(program)

    print(f'\n> {colorize(str(theme.updates), BOLD, BLUE)} apps updated')
    if theme.errors():
        print(f'> {colorize(str(theme.errors()), BOLD, RED)} apps with errors')


def main() -> int:
    args = Setup.init(APP_HOME)
    fn = get_filetheme(args.theme)
    if not (fn := get_filetheme(args.theme)):
        return handle_missing_theme(args.theme)

    theme = initialize_theme(args.theme, fn, args.dry_run)
    process_theme(theme, args.mode)

    return 0


if __name__ == '__main__':
    sys.exit(main())
