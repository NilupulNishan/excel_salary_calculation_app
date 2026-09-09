"""Entry point for the packaged executable.

PyInstaller runs its entry script as a top-level module named `__main__`, with
no package context -- so the relative imports inside `salary_app/__main__.py`
(`from .api import Api`) raise:

    ImportError: attempted relative import with no known parent package

Importing the module through its package instead gives it the context it needs.
`salary_app/__main__.py` stays idiomatic, and `python -m salary_app` keeps
working for development.
"""

from salary_app.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
