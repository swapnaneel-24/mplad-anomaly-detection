"""PEIARS backend application package.

FastAPI application for the Public Expenditure & Infrastructure Anomaly
Review System (PEIARS). This package is deliberately independent of the
frozen research package ``src/mplad``: no module under ``backend/app`` may
import ``mplad`` or any research dependency (NumPy, pandas, scikit-learn,
SciPy, matplotlib). Research artifacts will be integrated in later pull
requests through read-only, manifest-verified adapters only.
"""

#: Human-readable application name reported by ``GET /api/v1/meta``.
APP_NAME = "PEIARS API"

#: Backend application version (semantic, incremented per pull request).
__version__ = "0.2.0"
