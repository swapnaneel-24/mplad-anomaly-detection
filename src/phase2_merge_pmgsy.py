# “Ministry of Rural Development, 2022. PMGSY Rural Connectivity Datasets, https://geosadak-pmgsy.nic.in/opendata/. Published under India’s Government Open Data License: https://data.gov.in/government-open-data-license-india”

import pandas as pd
import geopandas as gpd
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

CORE_FILE = "PMGSY_Master_Dataset_Combined(1).csv"

CANDIDATES = {
    "Rajasthan": "Proposal_PMGSY-III_RAJASTHAN.shp",
    "Maharashtra": "Proposal_PMGSY-III_MAHARASHTRA.shp",
    "Odisha": "Proposal_PMGSY-III_ODISHA.shp"
}

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOAD FUNCTION
# ============================================================

def load_dataset(path, state_name):

    path = Path(path)

    if path.suffix.lower() == ".shp":
        gdf = gpd.read_file(path)
        df = pd.DataFrame(
            gdf.drop(columns="geometry", errors="ignore")
        )
    else:
        df = pd.read_csv(path)

    # Normalize column names
    df.columns = (
        df.columns
        .str.upper()
        .str.strip()
    )

    # Traceability only
    df["SOURCE_STATE"] = state_name

    return df


# ============================================================
# LOAD CORE
# ============================================================

print("=" * 80)
print("LOADING PMGSY STREAM B DATA")
print("=" * 80)

datasets = {}

core = load_dataset(
    CORE_FILE,
    "Bihar_UP_MP"
)

datasets["Bihar_UP_MP"] = core

print(
    f"Bihar_UP_MP: {len(core)} rows"
)


# ============================================================
# LOAD CANDIDATES
# ============================================================

for state, filename in CANDIDATES.items():

    try:
        df = load_dataset(
            filename,
            state
        )

        datasets[state] = df

        print(
            f"{state}: {len(df)} rows"
        )

    except Exception as e:

        raise RuntimeError(
            f"Could not load {state}: {e}"
        )


# ============================================================
# FIND COMMON SOURCE COLUMNS
# ============================================================

print("\n" + "=" * 80)
print("CHECKING COMMON COLUMNS")
print("=" * 80)

source_columns = [
    set(df.columns) - {"SOURCE_STATE"}
    for df in datasets.values()
]

common_columns = set.intersection(
    *source_columns
)

common_columns = sorted(common_columns)

print("\nCommon columns:")
print(common_columns)


# Check whether anything differs
for name, df in datasets.items():

    missing = (
        set(common_columns) -
        set(df.columns)
    )

    if missing:
        raise ValueError(
            f"{name} is missing: {missing}"
        )


# ============================================================
# CLEAN EACH DATASET
# ============================================================

cleaned = {}

print("\n" + "=" * 80)
print("DEDUPLICATION + P/L SPLIT")
print("=" * 80)

for name, df in datasets.items():

    df = df[common_columns + ["SOURCE_STATE"]].copy()

    before = len(df)

    df = df.drop_duplicates().copy()

    after = len(df)

    print(
        f"{name:15s} | "
        f"Before={before:5d} | "
        f"Removed={before-after:5d} | "
        f"Unique={after:5d}"
    )

    cleaned[name] = df


# ============================================================
# MERGE ALL UNIQUE RECORDS
# ============================================================

combined = pd.concat(
    cleaned.values(),
    ignore_index=True
)

print("\nCombined unique records:", len(combined))


# ============================================================
# CHECK CROSS-STATE EXACT DUPLICATES
# ============================================================

analysis_columns = [
    c for c in common_columns
    if c != "STATE_NAME"
]

cross_state_duplicates = (
    combined
    .duplicated(
        subset=analysis_columns,
        keep=False
    )
    .sum()
)

print(
    "Potential cross-state duplicate rows:",
    cross_state_duplicates
)

# Do NOT automatically remove these.
# They need semantic inspection if any exist.


# ============================================================
# SPLIT P / L
# ============================================================

if "PROPOSAL_T" not in combined.columns:
    raise ValueError(
        "PROPOSAL_T is required but missing."
    )

p_data = combined[
    combined["PROPOSAL_T"] == "P"
].copy()

l_data = combined[
    combined["PROPOSAL_T"] == "L"
].copy()


# ============================================================
# SAVE
# ============================================================

p_output = (
    OUTPUT_DIR /
    "pmgsy_stream_b_p_unique.csv"
)

l_output = (
    OUTPUT_DIR /
    "pmgsy_stream_b_l_unique.csv"
)

p_data.to_csv(
    p_output,
    index=False
)

l_data.to_csv(
    l_output,
    index=False
)


# ============================================================
# FINAL REPORT
# ============================================================

print("\n" + "=" * 80)
print("FINAL STREAM B DATASET")
print("=" * 80)

print(
    f"Total unique records : {len(combined)}"
)

print(
    f"P records            : {len(p_data)}"
)

print(
    f"L records            : {len(l_data)}"
)

print("\nState-wise P counts:")
print(
    p_data["SOURCE_STATE"]
    .value_counts()
    .sort_index()
    .to_string()
)

print("\nState-wise L counts:")
print(
    l_data["SOURCE_STATE"]
    .value_counts()
    .sort_index()
    .to_string()
)

print("\nSaved:")
print(p_output)
print(l_output)