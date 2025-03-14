<div align="center">
    <h1><b>💅 PyThemes</b></h1>
    <span>Simple cli tool for update themes, find/replace and execute commands</span>
<br>
<br>

![Python](https://img.shields.io/badge/python-3670A0?style=Flat&logo=python&logoColor=ffdd54)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
[![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy)
[![License - MIT](https://img.shields.io/badge/license-MIT-9400d3.svg)](https://spdx.org/licenses/)

</div>

## 📖 Description

I use a window manager `WM`, like [`dwm`](https://github.com/haaag/dwm), so I need to manage my themes, colorscheme manually.

This script will take care of that. It's designed to handle system and application themes, including `light` `dark` mode switching, wallpaper settings, and command execution.

## 🛠️ Usage

```sh
~ $ pythemes
usage: pythemes [-h] [-m MODE] [-l] [-a APP] [-L] [-d] [-v] [-t] [--verbose] [theme]

options:
    theme               select a theme
    -m, --mode          select a mode [light|dark]
    -l, --list          list available themes
    -a, --app           apply mode to app
    -L, --list-apps     list available apps in theme
    -d, --dry-run       simulate action
    -h, --help          print this help message

locations:
  /home/$USER/.config/pythemes
```

### 🎨 Apply theme/mode

```sh
~ $ pythemes gruvbox -m dark
> gruvbox theme with (10 apps)

[app] bat applied.
[app] rofi applied.
[app] xresources applied.
[app] fzf applied.
[app] gtk2-mine no changes needed.
[app] gtk3 applied.
[app] newsboat applied.
[app] nvim applied.
[app] git applied.
[app] zathura applied.
[cmd] dunst executed.
[cmd] xresources executed.
[wal] my-dark-wallpaper.jpg set.
[sys] dwm restarted.
[sys] st restarted.


```

### 🎨 Apply theme/mode to single app

```sh
~ $ pythemes gruvbox -m dark -a fzf
[app] fzf applied.

```

## 📦 Installation

```bash
# Clone repository
$ git clone "https://github.com/haaag/pythemes"
$ cd pythemes

# Create virtual environment & source
$ python -m venv .venv & source .venv/bin/activate

# Install
(.venv) $ pip install .
```

- Using [`uv`](https://github.com/astral-sh/uv) to install tool: <sub>(recommended)</sub>

```sh
~ $ cd /path/to/cloned/pythemes
~ $ uv tool install .
```

- Using [`pipx`](https://github.com/pypa/pipx) to install tool:

```sh
~ $ pipx install /path/to/cloned/pythemes
```

## 📝 Theme file

The theme file, is an `INI` file that has 3 sections for now.

- <b>program:</b> section for programs settings
- <b>wallpaper:</b> section for wallpapers settings
- <b>restart:</b> section for restart settings

### 🖥️ Program section

```ini
[program_name]:
file:     path to the file to update
query:    the query to find in the file
light:    the theme to use for the light theme
dark:     the theme to use for the dark theme
cmd:      the command to execute (optional)
```

### 🌄 Wallpaper section

```ini
[wallpaper]
light:    path to the wallpaper for the light theme
dark:     path to the wallpaper for the dark theme
random:   path to the directory with the wallpapers
cmd:      the command to execute
```

### 🔁 Restart section

Will search for `PIDs` <sub>process ids</sub> that match the `cmd` and send the signal `SIGUSR1`

```ini
[restart]
cmd:      commands that will receive the signal SIGUSR1
```

### 📝 Example

This is a example INI file for pythemes.

You can find the complete example [here](./example/gruvbox.ini)

```ini
; the script will read this file and find the `query` line and replace it with
; the `{theme}` value and then execute the `cmd` command if it  is set

[wallpaper]
light=~/wallpapers/my-light-wallpaper.png
dark=~/wallpapers/my-dark-wallpaper.png
random=~/dls/wallpapers/
cmd=nitrogen --save --set-zoom-fill

[bat]
file=~/.config/shell/some-envs.sh
query=export BAT_THEME="{theme}"
light=gruvbox-light
dark=gruvbox-dark

[rofi]
file=~/.config/rofi/config.rasi
query=@theme "{theme}"
light=gruvbox-light-hard
dark=gruvbox-dark

[restart]
cmd=dwm st
```
