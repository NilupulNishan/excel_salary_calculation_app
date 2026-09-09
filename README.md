# Softvil Salary Slips

A local Windows desktop app that turns the monthly payroll workbook into
payslip PDFs. Drop in the Excel file, review each employee, export.

Runs entirely offline. No server, no account, no data leaves the machine.

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
4. **Python 3.13**, Windows only.

---

## Building the .exe

```powershell
.venv\Scripts\pyinstaller.exe packaging\salary_app.spec --noconfirm
```

Produces `dist\SoftvilSalarySlips.exe` — about 24 MB, one file, no installer.
Copy it anywhere and run it; the target machine needs no Python.

To rebuild the app icon after changing the logo:

```powershell
.venv\Scripts\python.exe tools\make_icon.py
```

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

## Development

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

.venv\Scripts\python.exe -m salary_app      # run the app
.venv\Scripts\python.exe -m pytest          # 154 tests
```

| Command | What it does |
|---|---|
| `python -m salary_app` | Native app window |
| `python -m salary_app --debug` | Devtools plus verbose logging |
| `python -m salary_app --selftest` | Headless checks, then exit |
| `python -m salary_app --browser` | Dev only — default browser instead of a window |
| `python tools\make_sample.py` | Render a sample payslip to `out\` |
| `python tools\smoke_ui.py` | Drive the real window through JS (12 checks) |

`--browser` is a debugging aid, not a shipped feature; nothing is exposed on a
public interface.

### Dependencies

Runtime (`requirements.txt`): `openpyxl`, `reportlab`, `pypdfium2`, `pywebview`.

Development (`requirements-dev.txt`) adds `pytest` and `pymupdf`.

> **PyMuPDF is deliberately dev-only.** It is AGPL-3.0 and must never ship
> inside a distributed binary. `pypdfium2` (Apache-2.0) does the runtime PDF
> rendering. The split between the two requirements files is what enforces
> this — the spec also excludes it explicitly.

---

## Layout

```
salary_app/
  __main__.py     entry point, logging, WebView2 check, --selftest
  api.py          the bridge the UI calls into
  config.py       company details; resource paths that work frozen and unfrozen
  settings.py     user settings persisted to %APPDATA%
  excel_reader.py workbook -> Payslip records
  models.py       the Payslip record, field groups, validation
  money.py        Decimal coercion and display formatting
  numwords.py     amount -> words
  pdf/
    renderer.py   the payslip layout
    theme.py      fonts, palette, drawing primitives
    preview.py    PDF -> PNG for the on-screen preview
web/              index.html, styles.css, app.js, logo
packaging/        PyInstaller spec and app icon
tools/            sample renderer, icon builder, UI smoke test
tests/
```

`build/` and `dist/` are generated and gitignored — which is why the spec lives
in `packaging/` instead.

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

---

## Where files go

Payslips are written to a folder you choose on the upload screen, remembered in
`%APPDATA%\SoftvilSalarySlips\settings.json`. It defaults to
`Documents\Salary Slips`.

Settings live there rather than beside the executable because a frozen app may
sit in `Program Files`, which a normal user cannot write to. A missing, corrupt
or unreachable folder falls back to the default rather than blocking exports.

**Export All** writes every complete slip and reports the ones it skipped. A
slip missing an employee name is skipped rather than guessed — it would also
collide on filename with every other unnamed slip.

---

## Known issue in the source workbook

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

## Data handling

`.gitignore` excludes `*.xlsx`, `*.xlsm` and `Pay Slip*.pdf`. Payroll workbooks
contain real salaries and NIC numbers, and git history is effectively permanent
— a file committed once is not removed by deleting it in a later commit. Keep
reference files locally; do not commit them.
