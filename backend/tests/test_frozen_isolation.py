"""Frozen-research isolation guarantees.

Two distinct boundaries are enforced:

**Static boundary (source code).** No module under ``backend/app`` or
``backend/scripts`` may *import* the frozen research package ``mplad`` or
any research dependency (NumPy, pandas, scikit-learn, SciPy, matplotlib,
seaborn). This is checked by an AST scan of every ``.py`` file and is a
hard source-code rule: the backend must never depend on the research
stack at import time.

**Runtime boundary (loaded modules).** Importing the application must not
cause the frozen research package ``mplad`` to be loaded. This is checked
in a clean subprocess that snapshots ``sys.modules`` before and after
``import app.main`` and asserts that ``mplad`` is not among the
newly-loaded roots.

Why the runtime check targets ``mplad`` only — not NumPy/pandas:

  Independent review found that the broader runtime check (asserting that
  NumPy and Pandas are absent from ``sys.modules`` after importing the
  app) produced false positives in environments where those libraries are
  preloaded by the Python runtime itself — for example via ``sitecustomize``
  modules, ``.pth`` files, or data-science Python distributions that
  eagerly import common scientific packages at interpreter startup.  In
  such an environment NumPy and Pandas appear in ``sys.modules`` **before**
  the app is imported, so their presence says nothing about whether the
  app pulled them in.

  The actual architectural requirement (PR-02 §10/§11) is that *the API
  must not import or execute the frozen research package* ``mplad``.  The
  static AST scan already forbids the backend source from importing any
  research dependency; the runtime check therefore only needs to prove
  that ``mplad`` itself was not loaded as a side effect of importing the
  application — which is the real isolation invariant.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_ROOT / "app"
SCRIPTS_DIR = BACKEND_ROOT / "scripts"

#: Modules the backend source code must never import (static AST check).
#: ``mplad`` is the frozen research package; the rest are its research
#: dependencies. This is a source-code rule, not a runtime-environment rule.
FORBIDDEN_SOURCE_IMPORTS = {
    "mplad",
    "sklearn",
    "pandas",
    "numpy",
    "scipy",
    "matplotlib",
    "seaborn",
}

#: The frozen research package — the only module whose *runtime* loading
#: by the app is an isolation violation.  Research dependencies (NumPy
#: etc.) may be present in the environment without the app importing them;
#: the static AST scan already prevents the backend source from importing
#: them.
RUNTIME_FORBIDDEN_ROOTS = {"mplad"}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


class TestStaticImportBoundary:
    """The backend source must never import the research stack."""

    def test_backend_app_never_imports_frozen_research_code(self):
        offenders: dict[str, set[str]] = {}
        for path in sorted(APP_DIR.rglob("*.py")):
            roots = _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
            violations = roots & FORBIDDEN_SOURCE_IMPORTS
            if violations:
                offenders[str(path.relative_to(BACKEND_ROOT))] = violations
        assert not offenders, f"forbidden imports: {offenders}"

    def test_backend_scripts_never_import_frozen_research_code(self):
        offenders: dict[str, set[str]] = {}
        for path in sorted(SCRIPTS_DIR.glob("*.py")):
            roots = _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
            violations = roots & FORBIDDEN_SOURCE_IMPORTS
            if violations:
                offenders[str(path.relative_to(BACKEND_ROOT))] = violations
        assert not offenders, f"forbidden imports: {offenders}"


class TestRuntimeImportBoundary:
    """Importing the app must not load the frozen research package."""

    def test_importing_the_app_does_not_load_mplad(self):
        """Dynamic proof in a clean interpreter.

        Snapshots ``sys.modules`` before and after ``import app.main`` and
        asserts that ``mplad`` is not among the newly-loaded module roots.
        Only ``mplad`` (the frozen research package) is checked at runtime:
        research dependencies such as NumPy may be preloaded by the
        environment (sitecustomize, ``.pth`` files, data-science Python
        distributions) and their presence is not an isolation violation.
        The static AST scan in :class:`TestStaticImportBoundary` already
        prevents the backend source from importing them.
        """
        code = (
            "import sys; "
            f"sys.path.insert(0, r'{BACKEND_ROOT}'); "
            "before = set(sys.modules); "
            "import app.main; "
            "after = set(sys.modules); "
            "new_roots = {m.split('.')[0] for m in (after - before)}; "
            "loaded = new_roots & {'mplad'}; "
            "sys.exit(f'forbidden modules loaded by app: {sorted(loaded)}' if loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_mplad_not_in_sys_modules_after_app_import(self):
        """Belt-and-suspenders: ``mplad`` is absent from ``sys.modules``
        entirely after importing the app, regardless of what was loaded
        before."""
        code = (
            "import sys; "
            f"sys.path.insert(0, r'{BACKEND_ROOT}'); "
            "import app.main; "
            "roots = {m.split('.')[0] for m in sys.modules}; "
            "loaded = roots & {'mplad'}; "
            "sys.exit(f'mplad in sys.modules: {sorted(loaded)}' if loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_health_endpoints_answer_without_research_environment(self):
        """The ASGI app is exercisable end to end (no research imports needed)."""
        code = (
            "import sys; "
            f"sys.path.insert(0, r'{BACKEND_ROOT}'); "
            "from fastapi.testclient import TestClient; "
            "from app.core.config import Settings; "
            "from app.main import create_app; "
            "settings = Settings(_env_file=None, environment='test'); "
            "client = TestClient(create_app(settings=settings)); "
            "assert client.get('/api/v1/health/live').status_code == 200; "
            "assert client.get('/api/v1/health/ready').status_code == 200; "
            "assert client.get('/api/v1/meta').status_code == 200; "
            "assert client.get('/api/v1/sources').status_code == 200"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
