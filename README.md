# Softvil Salary Slips

A local Windows desktop app that turns the monthly payroll workbook into
payslip PDFs. Drop in the Excel file, review each employee, export.

Runs entirely offline. No server, no account, no data leaves the machine.

![The review screen: fields on the left, a live preview of the real PDF on the
right](docs/review-screen.png)

*The review screen. All names and figures shown are fabricated.*

---

## Requirements

- **Windows 10 or 11.** Windows-only; the payslip uses fonts Windows ships.
- **[Python 3.13](https://www.python.org/downloads/)** — to run from source or
  build the exe. Not needed to run a built `.exe`.
- **Edge WebView2 runtime** — part of Windows 11; see
  [The one external dependency](#the-one-external-dependency).

---

## Design rules

These are constraints, not preferences. Changes that break them are bugs.

1. **No AI or LLM anywhere.** Parsing and layout are deterministic.
2. **No payroll calculation.** Every money value is read from the sheet or
   typed by the user. Gross, Net, EPF, ETF and APIT are never derived. If the
   sheet is wrong, the payslip is wrong the same way — the app reports the
   disagreement rather than silently "fixing" a figure.
3. **Real text, never a picture of text.** The exported PDF is selectable,
   copyable and machine-extractable. Only the logo is a raster image.
4. **One source of truth for colour.** See [The design system](#the-design-system).
5. **Python 3.13**, Windows only.

---

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

.venv\Scripts\python.exe -m salary_app      # run the app
.venv\Scripts\python.exe -m pytest
```

| Command | What it does |
|---|---|
| `python -m salary_app` | Native app window |
| `python -m salary_app --debug` | Devtools plus verbose logging |
| `python -m salary_app --selftest` | Headless checks, then exit |
| `python -m salary_app --browser` | Dev only — default browser instead of a window |
| `python tools\make_sample.py` | Render a sample payslip to `out\` (colour + grayscale) |
| `python tools\make_tokens.py` | Regenerate `web\tokens.css` from the palette |
| `python tools\make_icon.py` | Rebuild the app icon from the logo |
| `python tools\smoke_ui.py` | Drive the real window through JS |
| `python tools\check_tokens_resolve.py` | Confirm every CSS token resolves in the real window |

`--browser` is a debugging aid, not a shipped feature; nothing is exposed on a
public interface.

**Why two UI tools rather than tests.** A `var()` naming a token that does not
exist resolves to nothing: the element renders unstyled, no error is raised,
and every unit test still passes. Likewise a JS exception on load leaves a
blank window that pytest cannot see. These two drive the real window and read
the computed result back.

### Dependencies

Runtime (`requirements.txt`): `openpyxl`, `reportlab`, `pypdfium2`, `pywebview`.

Development (`requirements-dev.txt`) adds `pytest` and `pymupdf`.

> **PyMuPDF is deliberately dev-only.** It is AGPL-3.0 and must never ship
> inside a distributed binary. `pypdfium2` (Apache-2.0) does the runtime PDF
> rendering. The split between the two requirements files is what enforces
> this — the spec also excludes it explicitly.

---

## Project layout

```
run_app.py          entry point for the PACKAGED exe (see Building)
salary_app/
  __main__.py       entry point for `python -m`; logging, WebView2 check, --selftest
  api.py            the bridge the UI calls into
  config.py         company details; resource paths that work frozen and unfrozen
  settings.py       user settings persisted to %APPDATA%
  excel_reader.py   workbook -> Payslip records
  models.py         the Payslip record, field groups, validation
  money.py          Decimal coercion and display formatting
  numwords.py       amount -> words
  pdf/
    renderer.py     the payslip layout
    theme.py        palette, type scale, fonts, drawing primitives
    preview.py      PDF -> PNG for the on-screen preview
web/
  index.html  app.js  styles.css
  tokens.css        GENERATED from theme.py — do not edit
  logo-sm-01.png
design/             design-system canvas sources (*.dc.html, canvas.json)
packaging/          PyInstaller spec and app icon
tools/              sample renderer, token generator, icon builder, UI checks
tests/
```

`build/`, `dist/` and `design/*.html` are generated and gitignored — which is
why the PyInstaller spec lives in `packaging/` rather than `build/`.

---

## How it reads the workbook

Only the sheet named **`Payment Summary`** is read; every other sheet is
ignored. Matching tolerates case and stray spaces. If that sheet is absent the
app fails loudly and names the sheets it did find — it never falls back to "the
first sheet", because reading the wrong tab would produce plausible-looking
payslips with wrong numbers.

The header row is found by **scoring** candidate rows against known column
names, not by assuming row 1. In the reference workbook the header is on row 3,
with a summary band above it and a totals row below.

Column names are matched with all whitespace stripped, and each field accepts
several spellings — real headers include `"Basic Salary "`, `"EPF(8%)"` versus
`"EPF (12%)"`, and the misspelling `"Net Earinings/Payable"`.

The `Total Paid` row is excluded. Reading a file is fast (~0.03s for an 866 KB
workbook) because the sheet is streamed and a run of blank rows stops the scan
— the reference file spans 9138 rows but holds only ten with data.

### Blank is not zero

`None` renders as empty (the line does not apply); `0` renders as `-` (the line
applies and is nil). Both appear on the reference payslip and mean different
things.

### Known issue in the source workbook

The workbook's Gross formula double-counts the Internship/Other allowance:

```
O = P + Q + R          (Total Allowance)
T = N + O + R + S      (Gross)   <-- R added twice
```

It is invisible while `R = 0`, which it currently is for every employee. The
moment someone receives an internship allowance, Gross and Net are both
overstated. This app does not calculate, so it will not silently correct the
number; it shows a warning badge instead. **Worth fixing in the spreadsheet.**

---

## The design system

The app chrome and the payslip are two renderers of one brand, so their tokens
live in one place: **`PALETTE` in `salary_app/pdf/theme.py`**.

```powershell
# after changing a colour in theme.PALETTE
.venv\Scripts\python.exe tools\make_tokens.py     # regenerates web\tokens.css
```

**Never add a colour or a radius to `styles.css`.** Add it to `theme.PALETTE`
and regenerate. `tests/test_design_tokens.py` fails if `tokens.css` is stale or
if the stylesheet declares a brand colour of its own — the two surfaces had
already drifted once, with the hairline at `#E2E8ED` in CSS against `#D8DEE4`
in the PDF.

**Type scale.** Six roles in `theme.py`, in points:

| Role | pt | Used for |
|---|---|---|
| `DISPLAY` | 30 | the page title |
| `FIGURE` | 19 | the net salary amount |
| `LEAD` | 10.5 | company name, employee name, period, values |
| `BODY` | 8.6 | designation, breakdown rows, totals |
| `FINE` | 7.4 | addresses, amount in words, footer |
| `MICRO` | 6.8 | every uppercase label (with `MICRO_TRACKING`) |

`renderer.py` carries no raw sizes; a test enforces it.

**Brand cyan is never text.** At 1.85:1 on white it is unreadable as type, so
it is confined to rules, bars and borders — asserted by a test, not left to
habit. Every text colour meets WCAG AA, also asserted.

**Letter-spacing goes through ReportLab's own draw methods**, never a
hand-rolled text object. Character spacing is PDF graphics state and is not
reset by ending a text object: applying it by hand leaked tracking into every
later string on the page and pushed the footer 19.6pt past the right margin.

---

## Where files go

Payslips are written to a folder you choose on the upload screen, remembered in
`%APPDATA%\SoftvilSalarySlips\settings.json`. It defaults to
`Documents\Salary Slips`.

Settings live there rather than beside the executable because a frozen app may
sit in `Program Files`, which a normal user cannot write to. A missing, corrupt
or unreachable folder falls back to the default rather than blocking exports.

On the employee list, **clicking a row** opens it for review; the row's button
downloads that slip. A row with missing fields shows the button dashed and
faded, with the reason on hover — clicking it opens Review rather than doing
nothing.

**Export All** writes every complete slip and reports the ones it skipped. A
slip missing an employee name is skipped rather than guessed — it would also
collide on filename with every other unnamed slip.

---

## Building the .exe

```powershell
.venv\Scripts\pyinstaller.exe packaging\salary_app.spec --noconfirm
```

Produces `dist\SoftvilSalarySlips.exe` — one file, roughly 25 MB, no installer.
Copy it anywhere and run it; the target machine needs no Python.

The spec's entry point is **`run_app.py`, not `salary_app/__main__.py`**:
PyInstaller runs its entry script as a top-level `__main__` with no package
context, so that module's relative imports raise `ImportError`.

### `PermissionError: [WinError 5] Access is denied`

The exe is still running. A onefile build leaves **two** processes — a parent
bootloader and the child that owns the window — so closing the window is not
always enough:

```powershell
Get-Process SoftvilSalarySlips* | Stop-Process -Force
```

### If it fails to start

A windowed build has no console, so startup errors are invisible. Two tools:

```powershell
# Does the packaged bundle actually work? Renders a PDF, rasterises it,
# checks the text layer -- all inside the frozen app.
dist\SoftvilSalarySlips.exe --selftest

# Then read the log it writes:
type %TEMP%\softvil-salary-slips.log
```

For a build that prints its own tracebacks:

```powershell
$env:SALARY_APP_CONSOLE = "1"
.venv\Scripts\pyinstaller.exe packaging\salary_app.spec --noconfirm
$env:SALARY_APP_CONSOLE = ""
```

That produces `dist\SoftvilSalarySlips-console.exe`, identical but with a
console attached.

### The one external dependency

PyInstaller bundles Python and every library, but the window itself is drawn by
the **Microsoft Edge WebView2 runtime**, a Windows component the .exe does not
contain. It ships as part of Windows 11, so on a Win11 machine nothing needs
installing. On older or stripped Windows the app detects it is missing and says
so in a dialog rather than falling back to a broken renderer.

---

## Limitations

Known and unresolved. Read these before trusting the app with a live payroll run.

- **The identity columns have never been read from a real file.** Columns B-M
  (`Name`, `EMP/EPF No:`, `Designation`, ...) were empty in every workbook used
  during development, so those slips were completed by typing into the review
  screen. The column mapping is covered by tests built on synthetic workbooks,
  but it has never parsed a production sheet with names in it. **This is the
  largest untested assumption in the project.**
- **"Salary Advance", not "Salary Adjustment".** The reference payslip printed
  *Salary Adjustment*; the sheet's column Z is *Salary Advance* and is what
  feeds Total Deductions. The app uses the sheet's wording. Change
  `DEDUCTION_LINES` in `pdf/renderer.py` if the old label is wanted.
- **Month and year come from the filename**, because the sheet carries neither
  (`Final Salary - August 2026.xlsx` -> August 2026). An unparseable name leaves
  them blank for the user to fill in.
- **Two people editing at once is not handled.** Settings and output are
  per-machine; nothing coordinates concurrent runs.
- **No amount is ever recalculated.** If a figure in the sheet is wrong, the
  payslip repeats it. The warning badge flags disagreements it can detect --
  it does not catch a wrong number that is internally consistent.

---

## If the app will not read your workbook

| It says | What to do |
|---|---|
| `This workbook has no "Payment Summary" sheet` | It lists the sheets it found. Rename the payroll sheet, or check you opened the right file. |
| `Could not find the payroll header` | The header row matched fewer than six known column names. Check the column titles against `COLUMN_ALIASES` in `excel_reader.py`. |
| `no employee rows below it` | Usually a workbook written by a script rather than saved from Excel, so formula results were never stored. Open it in Excel, save once, retry. |
| Rows load but money is blank | Same cause: cached formula values are missing. Save the file from Excel. |

---

## Data handling

`.gitignore` excludes `*.xlsx`, `*.xlsm` and `Pay Slip*.pdf`. Payroll workbooks
contain real salaries and NIC numbers, and git history is effectively permanent
— a file committed once is not removed by deleting it in a later commit. Keep
reference files locally; do not commit them.

---

## Licence

See [LICENSE](LICENSE).
