# pythemes

[![PyPI - Version](https://img.shields.io/pypi/v/pythemes.svg)](https://pypi.org/project/pythemes)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pythemes.svg)](https://pypi.org/project/pythemes)

---

**Table of Contents**

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install pythemes
```

## License

`pythemes` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Let's see

### File prototype

```dosini
[wallpaper]
light=~/dls/wallpapers/wallpaper-light.png
dark=~/dls/wallpapers/wallpaper-dark.png
random=~/dls/wallpapers/
cmd=nitrogen --save --set-zoom-fill

[xresources]
file=~/.config/X11/settings/theme.xresources
query=#define CURRENT_THEME {theme}
light=GRUVBOX_LIGHT_MEDIUM
dark=GRUVBOX_DARK_MEDIUM
cmd=xrdb -load ~/.config/X11/xresources

[fzf]
file=~/dot/fzf/themes/current.fzf
query=source "$DOTFILES/fzf/themes/{theme}.fzf"
light=gruvbox-light
dark=gruvbox-dark
cmd=
```
