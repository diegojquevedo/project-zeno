"""
Centralized dataset configuration to avoid circular imports.
"""

from pathlib import Path

import yaml

# Load datasets configuration once
ANALYTICS_DATASETS_PATH = Path(__file__).parent / "analytics_datasets.yml"
with open(ANALYTICS_DATASETS_PATH, encoding="utf-8") as f:
    DATASETS = yaml.safe_load(f)["datasets"]
