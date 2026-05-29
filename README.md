<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_header_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_header_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_header_light.webp" alt="" width="800">
  </picture>
</p>

<h1 align="center">🚚 Easy SCSModManager</h1>

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-E67E22?style=plastic&logo=python&logoColor=E67E22&labelColor=000000)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-E67E22?style=plastic&logo=linux&logoColor=E67E22&labelColor=000000)](https://www.python.org/)
[![Games](https://img.shields.io/badge/Games-ETS2%20%7C%20ATS-E67E22?style=plastic&labelColor=000000)](https://www.scssoft.com/)
[![License](https://img.shields.io/badge/License-GPL--3.0-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/Tests-276%20passed-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager)
[![i18n](https://img.shields.io/badge/i18n-🇬🇧%20🇩🇪-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager)

> **A proper mod manager for Euro Truck Simulator 2 and American Truck Simulator.**
> Browse your mods, sort the active load order with real drag and drop, and save it back to your profile - with automatic backups.

<p align="center">
  <a href="README_DE.md">
    <img src="https://img.shields.io/badge/🇩🇪_Auf_Deutsch_lesen-E67E22?style=for-the-badge&labelColor=000000" alt="Auf Deutsch lesen" height="35">
  </a>
</p>

<!-- Hero Screenshot -->
<!-- TODO: replace with 01_en_main_window.webp once the English screenshot exists -->
<p align="center">
  <img src="easy_scsmodmanager/resources/screenshots/01_de_main_window.webp" alt="Easy SCSModManager - Main Window" width="900">
</p>


<h3 align="center">💛 Support This Project</h3>

If this manager saves you time wrangling your mod list, consider supporting its development. Every contribution - no matter how small - helps keep the project alive.

<p align="center">
  <a href="https://www.paypal.com/donate/?hosted_button_id=HWPG6YAGXAWJJ">
    <img src="easy_scsmodmanager/resources/images/paypal.webp" alt="Support us on PayPal" height="80">
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://ko-fi.com/S6S51T9G3Y">
    <img src="easy_scsmodmanager/resources/images/ko-fi.webp" alt="Support us on Ko-fi" height="80">
  </a>
</p>

<p align="center"><i>Thank you to everyone who has already contributed - you're amazing! 🙏</i></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>


<h2 align="center">✨ What it does</h2>

- **Finds every mod you own** - reads your local `mod/` folder and your Steam Workshop subscriptions for both ETS2 and ATS, on Linux and Windows
- **ETS2-style browser** - a card grid with thumbnails, search, sort and multi-select (Ctrl / Shift)
- **Real drag and drop** - drag mods between the library and the active list, reorder the load order by dragging, with smooth scrolling and a clear drop indicator
- **Writes your load order back** - saves the active mod list straight into your `profile.sii`, so the game starts with exactly the order you set
- **Automatic backups** - every save can take a backup first, and you can restore any earlier profile with one click
- **Profile manager** - switch between your profiles and see which mods each one uses
- **Both games, one app** - ETS2 and ATS from day one, with a game switcher in the UI


<h2 align="center">🛣️ Planned</h2>

- Conflict detection via def-file overlap analysis
- Mod presets / load-order profiles you can share
- Workshop update notifications and one-click links to the Workshop page


<h2 align="center">🚀 Getting started</h2>

```bash
git clone https://github.com/Switch-Bros/easy-scsmodmanager.git
cd easy-scsmodmanager
pip install -e .
python -m easy_scsmodmanager
```

Requires Python 3.12+ and PyQt6. Standalone Linux AppImage and Windows builds are planned.


<h2 align="center">📜 License</h2>

[GPL-3.0-or-later](LICENSE) - Copyright © 2026 Switch Bros.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_footer_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_footer_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_footer_light.webp" alt="" width="800">
  </picture>
</p>

<p align="center">
  Made with ❤️ on Linux by <a href="https://github.com/Switch-Bros">Switch Bros</a>
</p>
