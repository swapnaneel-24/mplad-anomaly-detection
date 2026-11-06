"""Schema and integrity validation for Stream A feature matrices."""
from __future__ import annotations
from typing import Sequence
import numpy as np
import pandas as pd
from mplad.common import config

class FeatureMatrixError(ValueError):
    """A feature matrix violates the frozen FS-A contract."""

def validate_feature_matrix(
    fs_df: pd.DataFrame,
    expected_features: Sequence[str] = config.EXPECTED_FEATURE_COLUMNS,
    id_column: str = config.ID_COLUMN,
    forbidden_columns: Sequence[str] = config.FORBIDDEN_COLUMNS,
) -> list:
    """Validate a Stream A feature matrix; return ordered feature columns."""
    if not isinstance(fs_df, pd.DataFrame):
        raise FeatureMatrixError(f"Expected a pandas DataFrame, got {type(fs_df).__name__}.")

    columns = list(fs_df.columns)
    problems = []

    if id_column not in columns:
        problems.append(f"missing id column '{id_column}'")

    present_forbidden = [c for c in forbidden_columns if c in columns]
    if present_forbidden:
        problems.append("forbidden label column(s) present: " + ", ".join(f"'{c}'" for c in present_forbidden))

    missing_features = [c for c in expected_features if c not in columns]
    if missing_features:
        problems.append("missing expected feature column(s): " + ", ".join(missing_features))

    id_and_features = {id_column, *expected_features}
    unexpected = [c for c in columns if c not in id_and_features]
    if unexpected:
        problems.append("unexpected extra column(s): " + ", ".join(unexpected))

    if problems:
        raise FeatureMatrixError(_format_problems(problems, "schema"))

    problems = []
    if fs_df[id_column].isna().any():
        problems.append(f"'{id_column}' contains missing values")

    duplicated = fs_df[id_column][fs_df[id_column].duplicated()]
    if not duplicated.empty:
        problems.append(f"'{id_column}' contains {len(duplicated)} duplicate value(s)")

    expected_list = list(expected_features)
    present_features = [c for c in expected_list if c in columns]
    
    non_numeric = [c for c in present_features if not pd.api.types.is_numeric_dtype(fs_df[c])]
    if non_numeric:
        problems.append("non-numeric column(s): " + ", ".join(non_numeric))
    else:
        is_finite = np.isfinite(fs_df[present_features])
        non_finite = ~is_finite
        non_finite_counts = non_finite.sum()
        bad_cols = non_finite_counts[non_finite_counts > 0]
        if not bad_cols.empty:
            problems.append(
                "non-finite values (NaN, +inf, -inf) in column(s): "
                + ", ".join(f"{c} ({int(n)})" for c, n in bad_cols.items())
            )

    if problems:
        raise FeatureMatrixError(_format_problems(problems, "integrity"))

    return expected_list

def _format_problems(problems: list, category: str) -> str:
    lines = [f"Feature matrix validation failed ({category}):"]
    lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
    return "\n".join(lines)
