"""Softvil salary slip generator.

A local Windows desktop app: read the monthly payroll workbook, review each
employee, export payslip PDFs. Runs entirely offline.

Design rules this package obeys:
  * No AI/LLM anywhere -- deterministic parsing and layout only.
  * No payroll calculation -- every money value is read from the sheet or
    typed by the user. Gross, Net, EPF, ETF and APIT are never derived here.
  * PDF output carries a real text layer, never a picture of text.
"""

__version__ = "0.1.0"
