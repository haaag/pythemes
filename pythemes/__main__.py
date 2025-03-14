from __future__ import annotations

import argparse
import configparser
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
from typing import Self

__appname__ = 'pythemes'
__version__ = 'v0.1.6'

logger = logging.getLogger(__name__)

INISection = dict[str, str]
INIData = dict[str, INISection]


# app
APP_ROOT = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
APP_HOME = APP_ROOT / __appname__.lower()
PROGRAMS_RESTART: list[str] = []
HELP = textwrap.dedent(
    f"""Usage: {__appname__} [-h] [-m MODE] [-l] [-a APP] [-L] [-d] [-v] [-c COLOR] [--diff] [--verbose] [theme]

    Simple CLI tool for update themes files, with find/replace and execute commands.

Options:
    theme               Theme name
    -m, --mode          Select a mode [light|dark]
    -l, --list          List themes found
    -a, --app           Apply mode to app
    -D, --diff          Show app diff
    -L, --list-apps     List available apps in theme
    -d, --dry-run       Do not make any changes
    -c, --color         Enable color [always|never] (default: always)
    -V, --version       Print version and exit
    -v, --verbose       Increase output verbosity
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


class ThemeModeError(Exception):
    pass


class InvalidFilePathError(Exception):
    pass


class BaseError:
    """Represents an error"""

    mesg: str = ''
    occurred: bool = False


class Differ:
    """Represents a diff between two strings"""

    def changes(self, old: str, new: str) -> str:
        return self.process(old, new)

    def changes_with_indicators(self, old: str, new: str) -> str:
        return self.process(old, new, with_indicators=True)

    def process(self, old: str, new: str, with_indicators: bool = False) -> str:
        if old == new:
            return old

        r: list[str] = []
        diff = difflib.ndiff(old.splitlines(), new.splitlines())
        for line in diff:
            if line.startswith('+ '):
                r.append(colorize(line, GREEN))
            elif line.startswith('- '):
                r.append(colorize(line, RED))
            elif with_indicators:
                if line.startswith('?'):
                    r.append(line.strip())
                    continue
                # unchanged line
                r.append(colorize(line.strip(), ITALIC, GRAY))
        return '\n'.join(r)


@dataclass(slots=True)
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
            parse_restart(self.config)
            parse_wallpaper(self.config, self._data)
            parse_raw_program(section, self.config, self._data)

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
    """Parses the 'wallpaper' section from a `ConfigParser`."""
    section = 'wallpaper'
    if not p.has_section(section):
        return

    data[section] = {}
    for opt in ['light', 'dark', 'random', 'cmd']:
        if not p.has_option(section, opt):
            continue
        data[section][opt] = p.get(section, opt)
    p.remove_section(section)


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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


@dataclass(slots=True)
class Commander:
    """
    A collection of commands to execute or log.
    """

    cmds: list[Cmd] = field(default_factory=list)

    def register(self, cmd: Cmd) -> None:
        """Register a new command to the collection."""
        self.cmds.append(cmd)

    def add(self, app: App) -> None:
        """Add commands from an app if available."""
        if app.cmd is not None:
            self.register(app.cmd)

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
        if '~' not in command or not command:
            return command

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


@dataclass(slots=True)
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
    cmd: Cmd | None
    dry_run: bool
    original: str = ''
    status: str = ''
    _line_idx: int = -1
    _next_theme: str = ''
    error: BaseError = field(default_factory=BaseError)
    _lines: list[str] = field(default_factory=list)
    _diff: Differ = field(default_factory=Differ)

    @property
    def path(self) -> Path:
        """Returns the expanded path to the configuration file."""
        return Files.get_path(self.file)

    @property
    def lines(self) -> list[str]:
        """Returns the lines read from the configuration file."""
        return self._lines

    def read_lines(self) -> None:
        self._lines = Files.readlines(self.path)

    def update(self, mode: str) -> None:
        """
        Updates the configuration file with the next theme value if changes are detected.
        If in dry-run mode, logs the action without making changes.
        """
        if not self.has_changes(mode):
            self.status = colorize('no changes', ITALIC, YELLOW)
            return
        if not self._next_theme:
            self.status = colorize('err not updated', ITALIC, RED)
            logger.error(f'{self.name}: no next theme')
            return
        if self.dry_run:
            self.status = colorize('dry run', ITALIC, CYAN)
            return

        self.replace(self._line_idx, self._next_theme)

        Files.savelines(self.path, self.lines)

        self.status = colorize('applied', ITALIC, BLUE)

    def replace(self, index: int, string: str) -> None:
        """
        Replaces a line in the configuration file at the specified
        index with the given string.
        """
        self._lines[index] = string

    def find_current_theme(self) -> tuple[int, str | None]:
        """Finds the current theme in the file and returns its index and value."""
        self.read_lines()
        if not self.lines:
            self.error.mesg = f'file {self.path.as_posix()!r} is empty.'
            self.error.occurred = True
            return -1, None

        idx, current_theme = find(self.query, self.lines)
        if idx == -1:
            self.error.mesg = (
                f'{self.name}: query={self.query!r} not found in {self.path.as_posix()!r}.'
            )
            self.error.occurred = True
            return -1, None

        return idx, current_theme

    def determine_next_theme(self, current_theme: str, mode: str) -> str:
        """Determines the next theme based on the mode."""
        theme_mode = self.get_mode(mode)
        if not theme_mode:
            err_msg = f'invalid mode {mode!r}'
            raise ThemeModeError(err_msg)

        original = self.lines[self._line_idx]
        return original.replace(current_theme, theme_mode)

    def has_changes(self, mode: str) -> bool:
        """Checks if there are changes to be applied."""
        idx, current_theme = self.find_current_theme()
        if idx == -1 or current_theme is None:
            return False

        self._line_idx = idx
        self.original = self.lines[self._line_idx]
        next_theme = self.determine_next_theme(current_theme, mode)
        self._line_idx = idx
        self._next_theme = next_theme

        if current_theme == mode:
            return False

        return self.original != next_theme

    def get_mode(self, mode: str) -> str | None:
        """Returns the theme value for the specified mode."""
        match mode:
            case 'light':
                return self.light
            case 'dark':
                return self.dark
            case _:
                logger.error(f'invalid mode {mode!r}')
                return None

    def validate(self) -> Self:
        """Validates the application."""
        if not self.file:
            self.error.mesg = 'no file specified.'
            self.error.occurred = True
            return self
        if not self.dark:
            self.error.mesg = 'no dark theme specified.'
            self.error.occurred = True
        if not self.light:
            self.error.mesg = 'no light theme specified.'
            self.error.occurred = True
        if not self.query:
            self.error.mesg = 'no query specified.'
            self.error.occurred = True
            return self
        if '{theme}' not in self.query:
            self.error.mesg = "query does not contain placeholder '{theme}'."
            self.error.occurred = True
            return self
        if not self.path.exists():
            self.error.mesg = f"filepath '{self.path!s}' do not exists."
            self.error.occurred = True
            return self
        self.find_current_theme()
        return self

    def diff(self, mode: str) -> str:
        """Returns the difference between the current and next themes."""
        if not mode:
            return ''
        if self.error.occurred:
            self.status = colorize('has err', ITALIC, RED)
            logger.warning(f'{self.name}: {self.error.mesg}')
            return ''
        if not self.has_changes(mode):
            self.status = colorize('no changes', ITALIC, YELLOW)
            return ''
        self.status = colorize('has changes', ITALIC, CYAN)

        idx_start = max(0, self._line_idx - 2)
        idx_end = min(len(self.lines), self._line_idx + 2)
        original_chunk = ''.join(self.lines[idx_start:idx_end])
        new_chunk = original_chunk.replace(self.original, self._next_theme)

        return self._diff.changes_with_indicators(original_chunk, new_chunk)

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
        return f'{colorize("[app]", BOLD, c)} {self.name} {self.status}'


@dataclass(slots=True)
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
    error: BaseError = field(default_factory=BaseError)

    def randx(self) -> Path:
        """Randomly selects a wallpaper."""
        if not self.random.exists():
            err_msg = f'random wallpaper path {self.random!s} not found.'
            raise FileNotFoundError(err_msg)
        if self.random.is_file():
            err_msg = f'random wallpaper path {self.random!s} is not a directory.'
            raise NotADirectoryError(err_msg)
        files = list(self.random.glob('*.*'))
        if not files:
            err_msg = f'no files found in random wallpaper path {self.random!s}.'
            raise FileNotFoundError(err_msg)
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
        if self.error.occurred:
            print(self, 'wallpaper', colorize('err', ITALIC, RED))
            logger.warning(f'wallpaper: {self.error.mesg}')
            return
        if not path.is_file():
            err_msg = f'wallpaper={path} is not a file'
            raise InvalidFilePathError(err_msg)

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
        dark = data.get('dark', '')
        light = data.get('light', '')
        random = data.get('random', '')
        wall = cls(
            dark=Files.get_path(dark),
            light=Files.get_path(light),
            random=Files.get_path(random),
            cmd=data.get('cmd', ''),
            dry_run=dry_run,
        )

        if not dark:
            wall.error.mesg = "no 'dark' wallpaper specified."
        if not light:
            wall.error.mesg = "no 'light' wallpaper specified."
        if not random:
            wall.error.mesg = "no 'random' wallpaper specified."
        if not wall.cmd:
            wall.error.mesg = "no 'cmd' wallpaper specified."
        if wall.error.mesg:
            wall.error.occurred = True

        return wall

    def __str__(self) -> str:
        c = GREEN
        if self.error.occurred:
            c = RED
        return colorize('[wal]', BOLD, c)


@dataclass(slots=True)
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

    def load(self) -> Self:
        self.inifile.read().parse()
        return self

    def parse_apps(self) -> None:
        if not self.inifile.data:
            msg_err = f'no data found in {self.inifile.filepath!r}'
            raise ValueError(msg_err)

        if self.inifile.data.get('wallpaper', False):
            self.wallpaper = Wallpaper.new(
                self.inifile.data.pop('wallpaper'),
                dry_run=self.dry_run,
            )

        for name, values in self.inifile.data.items():
            values['name'] = name

            if not values.get('file') and not values.get('query') and name != 'wallpaper':
                cmd = ModeAction.new(values, dry_run=self.dry_run)
                self.register_cmd(cmd)
                continue

            f = values.get('file')
            if f is None or f == '':
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
        return App.new(section, dry_run=self.dry_run).validate()

    def errors(self) -> int:
        """Returns the total number of errors in the theme."""
        return sum(app.error.occurred for app in self.apps.values())

    def print(self) -> None:
        print(f'{GRAY}>{END} {self}', end='\n\n')

    def list(self) -> None:
        for app in self.apps.values():
            print(app)

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
        if len(pids) == 0:
            return
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
            logger.debug(f'found theme_value={theme_value!r} in line={line!r}')
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
        print(f'{GRAY}>{END} no themes found')
        return

    max_len = max(len(t.stem) for t in themes_files)
    for fn in themes_files:
        ini = INIFile(fn)
        theme = Theme(fn.stem, ini, dry_run=True).load()
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
    theme.load()
    theme.parse_apps()
    theme.print()

    for app in theme.apps.values():
        print(app)

    return 0


def get_app(theme: Theme, args: argparse.Namespace) -> App | None:
    """Returns an App from the given Theme."""
    if not args.app:
        logger.warning('no app specified')
        return None
    if not args.mode:
        logger.warning('no mode specified (dark|light)')
        return None
    if not (app := theme.get(args.app)):
        logger.warning(f'app {args.app!r} not found')
        return None
    return app


def parse_and_exit(args: argparse.Namespace, theme: Theme) -> None:
    """Parses command-line arguments and performs corresponding actions."""
    if args.version:
        version()
        sys.exit(0)
    if args.help:
        print(HELP)
        sys.exit(0)
    if args.list_apps:
        theme.print()
        theme.list()
        sys.exit(0)
    if args.diff:
        sys.exit(diff_app(theme, args))
    if args.app:
        sys.exit(update_app(theme, args))
    if args.list:
        version()
        print('\nThemes found:')
        print_list_themes()
        sys.exit(0)


def process_app(app: App, mode: str | None) -> None:
    """Process an app and update it if needed."""
    if not mode:
        logme('no mode specified (dark|light)')
        sys.exit(1)
        return
    if app.error.occurred:
        app.status = colorize('has err', ITALIC, RED)
        logger.warning(f'{app.name}: {app.error.mesg}')
        return
    app.update(mode)


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
        return args

    @staticmethod
    def logging(verbose: int) -> None:
        """
        Configures the logging format and level based on the debug flag.
        """
        logging_format = '[{levelname:^7}] {name:<18}: {message} (line:{lineno})'
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
        """Parses and returns command-line arguments."""
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False,
        )
        parser.add_argument('theme', nargs='?')
        parser.add_argument('-m', '--mode', type=str, choices=['dark', 'light'])
        parser.add_argument('-l', '--list', action='store_true')
        parser.add_argument('-a', '--app', type=str)
        parser.add_argument('-D', '--diff', action='store_true')
        parser.add_argument('--color', type=str, choices=['always', 'never'], default='always')
        parser.add_argument('-L', '--list-apps', action='store_true')
        parser.add_argument('-d', '--dry-run', action='store_true')
        parser.add_argument('-V', '--version', action='store_true')
        parser.add_argument('-h', '--help', action='store_true')
        parser.add_argument('-v', '--verbose', action='count', default=0)
        args = parser.parse_args()
        if args.diff and not args.app:
            print(f"{__appname__}: '--diff' requires '--app' (-a)", file=sys.stderr)
            sys.exit(1)
        return args


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
    theme = Theme(theme_name, ini, dry_run=dry_run).load()
    theme.parse_apps()
    return theme


def process_theme(theme: Theme, mode: str) -> None:
    """Processes theme apps, executes commands, and handles updates."""
    theme.print()
    commander = Commander()

    for app in theme.apps.values():
        process_app(app, mode)
        print(app)
        if app.error.occurred:
            continue
        commander.add(app)
        # time.sleep(0.005)
        theme.updates += 1

    handle_theme_updates(theme, commander, mode)


def handle_theme_updates(theme: Theme, commander: Commander, mode: str) -> None:
    """Handles updates, executes commands, and restarts necessary programs."""
    n_errors = theme.errors()
    if hasattr(theme, 'wallpaper'):
        theme.wallpaper.set(mode)
        if theme.wallpaper.error.occurred:
            n_errors += 1

    if not theme.has_updates:
        print('\n> no apps updated')
        return

    for cmd in theme.cmds:
        cmd.load(mode)

    if commander.has_cmds():
        commander.run()

    for program in PROGRAMS_RESTART:
        SysOps.restart(program)

    print(f'{GRAY}\n>{END} {colorize(str(theme.updates), BOLD, BLUE)} apps updated')
    if n_errors:
        print(f'{GRAY}>{END} {colorize(str(n_errors), BOLD, RED)} errors occurred')


def diff_app(theme: Theme, args: argparse.Namespace) -> int:
    if not (app := get_app(theme, args)):
        return 1
    if not (diff := app.diff(args.mode)):
        print(app)
        return 1
    print(app)
    print(diff)

    return 0


def update_app(theme: Theme, args: argparse.Namespace) -> int:
    if not (app := get_app(theme, args)):
        return 1
    process_app(app, args.mode)
    print(app)
    return 0


def main() -> int:
    args = Setup.init(APP_HOME)
    if not args.theme:
        print(HELP)
        return 1
    if not (fn := get_filetheme(args.theme)):
        return handle_missing_theme(args.theme)

    theme = initialize_theme(args.theme, fn, args.dry_run)
    parse_and_exit(args, theme)
    process_theme(theme, args.mode)

    return 0


if __name__ == '__main__':
    sys.exit(main())
