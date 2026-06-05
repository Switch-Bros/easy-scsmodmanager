# Contributing to Easy SCSModManager

Thanks for taking the time to help out. This project is a cross-platform mod
and profile manager for Euro Truck Simulator 2 and American Truck Simulator,
written in Python with PyQt6. Bug reports, translations, and pull requests are
all welcome.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting set up

You need Python 3.13 or newer. Pick whichever workflow you like.

### Classic venv

```bash
git clone https://github.com/Switch-Bros/easy-scsmodmanager.git
cd easy-scsmodmanager
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### uv

[uv](https://docs.astral.sh/uv/) is a fast drop-in for pip/venv. A committed
`uv.lock` pins an identical environment for every contributor.

```bash
git clone https://github.com/Switch-Bros/easy-scsmodmanager.git
cd easy-scsmodmanager
uv sync                            # creates .venv and installs from the lock
# or, without the lock:
uv venv && uv pip install -e ".[dev]"
```

Run the app with `python -m easy_scsmodmanager`.

## Running the tests

The suite uses pytest and pytest-qt. Qt runs headless, so set the offscreen
platform:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

Install the pre-commit hooks once so formatting and type checks run on every
commit:

```bash
pre-commit install
```

## Code standards

- **Formatting and linting:** `black`, `ruff`, and `mypy` must all pass. The
  pre-commit hooks enforce this; run `pre-commit run --all-files` if unsure.
- **Tests first (TDD):** write a failing test, then the code that makes it
  pass. New behaviour ships with tests.
- **Internationalisation is mandatory:** no hardcoded user-facing strings.
  Every label, message, and tooltip goes through `t("some.key")`, with the
  text living in `easy_scsmodmanager/resources/i18n/en/main.json` and
  `de/main.json`. Both language files must carry the same keys.
- **No stray paths:** filesystem locations for the games live in
  `easy_scsmodmanager/core/game_paths.py` only. Do not hardcode paths
  elsewhere.
- **Keep files small:** split a module before it grows unwieldy (well under
  500 lines).
- Avoid characters that are awkward to type on a normal keyboard (no em dash,
  smart quotes, or fancy arrows) in code and strings.

## Branches and pull requests

1. Fork the repository and create a topic branch off `main`
   (`git checkout -b fix-workshop-detection`).
2. Make focused commits - one logical change per commit, with a clear message.
3. Make sure the full test suite and the pre-commit hooks are green.
4. Open a pull request against `main` describing what changed and why. Link any
   related issue.

## Translations

Adding or updating a translation needs no coding. The full walk-through lives
in the [Translations section of the README](README.md#-translations): copy the
`en/` locale folder, translate the values (never the keys), and open a pull
request.

## Reporting bugs

Open a [GitHub issue](https://github.com/Switch-Bros/easy-scsmodmanager/issues).
Include your OS, how you installed the app (AppImage, Windows exe, deb, rpm,
AUR, tar.gz, or from source), and the relevant lines from the log file
(**Tools -> Open Log Folder**).
