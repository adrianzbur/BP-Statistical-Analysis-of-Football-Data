"""Input/output helpers for tabular football data."""

from pathlib import Path

import pandas as pd


def load_tabular_data(path: str | Path) -> pd.DataFrame:
    """Load a CSV or Parquet file into a dataframe.

    The function deliberately does not infer a football-specific schema.
    Schema validation belongs to the preprocessing step.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Data file does not exist: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(file_path)
    raise ValueError("Unsupported tabular format. Use CSV or Parquet.")
