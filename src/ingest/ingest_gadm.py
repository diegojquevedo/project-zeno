import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from sqlalchemy import create_engine, text

import src.shared.env  # noqa: F401
from src.core.logging import get_logger
from src.ingest.utils import (
    create_geometry_index_if_not_exists,
    create_id_index_if_not_exists,
    create_text_search_index_if_not_exists,
)
from src.shared.geocoding_helpers import GADM_LEVELS, SOURCE_ID_MAPPING

logger = get_logger(__name__)
GADM_ZIP_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"


LAYER_SUBTYPES = {
    "ADM_0": "country",
    "ADM_1": "state-province",
    "ADM_2": "district-county",
    "ADM_3": "municipality",
    "ADM_4": "locality",
    "ADM_5": "neighbourhood",
}

# Layer-specific chunk sizes to handle large geometries at higher admin levels
LAYER_CHUNK_SIZES = {
    "ADM_0": 10,  # Smallest batch for countries (largest geometries)
    "ADM_1": 100,  # Small batch for states/provinces
    "ADM_2": 1000,  # Medium batch for districts/counties
    "ADM_3": 5000,  # Larger batch for municipalities
    "ADM_4": 8000,  # Large batch for localities
    "ADM_5": 10000,  # Largest batch for neighbourhoods (smallest geometries)
}


def download(url: str, dest: str) -> str:
    """Stream-download *url* into *dest* (skips if already present)."""
    dest = Path(dest)
    if dest.exists():
        logger.info("Using cached file", path=str(dest))
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading", url=url, dest=str(dest))
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    size_mb = dest.stat().st_size / 1e6
    logger.info("Downloaded", path=str(dest), size_mb=round(size_mb, 1))
    return dest


def extract_gpkg(zip_path: Path, out_dir: Path) -> Path:
    """Unzip and return the GeoPackage path."""
    logger.info("Extracting", zip_path=str(zip_path), out_dir=str(out_dir))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out_dir)
    gpkg = out_dir / "gadm_410-levels.gpkg"
    if not gpkg.exists():
        raise FileNotFoundError("GeoPackage not found after extraction.")
    logger.info("Extracted", gpkg=str(gpkg))
    return gpkg


def process_chunk(
    chunk: gpd.GeoDataFrame, subtype: str, all_columns: set
) -> gpd.GeoDataFrame:
    """Process a single chunk of data."""
    # Set CRS to EPSG:4326
    chunk = chunk.to_crs("EPSG:4326")

    chunk["subtype"] = subtype

    # Build a single display name, ignoring NaNs / empty strings
    # Only use columns that exist in this layer
    all_name_cols = [
        "NAME_5",
        "NAME_4",
        "NAME_3",
        "NAME_2",
        "NAME_1",
        "COUNTRY",
    ]
    name_cols = [col for col in all_name_cols if col in chunk.columns]

    chunk["name"] = chunk.apply(
        lambda row: ", ".join(
            str(v)
            for v in (row[c] for c in name_cols)
            if pd.notna(v) and v != ""
        ),
        axis=1,
    )

    chunk["gadm_id"] = chunk.apply(
        lambda row: row[GADM_LEVELS[subtype]["col_name"]], axis=1
    )

    # Ensure all columns exist with None values for missing ones
    for col in all_columns:
        if col not in chunk.columns and col != "geometry":
            chunk[col] = None

    return chunk


def get_unified_schema(gpkg: Path) -> set:
    """Sample all layers to get a unified set of all possible columns."""
    all_columns = set()

    for layer in LAYER_SUBTYPES.keys():
        logger.info("Sampling schema", layer=layer)
        sample = gpd.read_file(gpkg, layer=layer, rows=1)
        all_columns.update(sample.columns)

    logger.info("Found columns", count=len(all_columns))
    return all_columns


def ingest_gadm_chunked(
    gpkg: Path, table_name: str = "geometries_gadm", chunk_size: int = 10000
) -> None:
    """Read GADM layers in chunks and ingest directly to PostGIS.
    Uses layer-specific chunk sizes to handle large geometries at higher admin levels.
    """
    from src.core.config import settings

    database_url = settings.get_database_url_for_psycopg2()
    engine = create_engine(database_url)

    # Ensure PostGIS extension is enabled
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

    # Get unified schema from all layers
    all_columns = get_unified_schema(gpkg)

    first_chunk = True
    total_processed = 0

    for layer, subtype in LAYER_SUBTYPES.items():
        logger.info("Processing layer", layer=layer)

        layer_chunk_size = LAYER_CHUNK_SIZES.get(layer, chunk_size)
        logger.debug("Chunk size", layer=layer, chunk_size=layer_chunk_size)

        total_rows = len(gpd.read_file(gpkg, layer=layer, rows=0))
        logger.info("Layer stats", layer=layer, total_rows=total_rows)

        # Process layer in chunks
        for start_idx in range(0, total_rows, layer_chunk_size):
            end_idx = min(start_idx + layer_chunk_size, total_rows)

            # Read chunk
            chunk = gpd.read_file(
                gpkg, layer=layer, rows=slice(start_idx, end_idx)
            )

            # Process chunk
            processed_chunk = process_chunk(chunk, subtype, all_columns)

            # Write to database
            if_exists_param = "replace" if first_chunk else "append"
            processed_chunk.to_postgis(
                table_name, engine, if_exists=if_exists_param, index=False
            )
            first_chunk = False

            total_processed += len(processed_chunk)
            logger.info(
                "Processed layer chunk",
                layer=layer,
                end_idx=end_idx,
                total_rows=total_rows,
                total_processed=total_processed,
            )

    logger.info("Ingested to PostGIS", table=table_name, records=total_processed)

    # Create spatial index on geometry column
    create_geometry_index_if_not_exists(
        table_name=table_name,
        index_name=f"idx_{table_name}_geom",
        column="geometry",
    )

    # Create text search index on name column
    create_text_search_index_if_not_exists(
        table_name=table_name,
        index_name=f"idx_{table_name}_name_gin",
        column="name",
    )

    # Create ID index on gadm_id column
    id_column = SOURCE_ID_MAPPING["gadm"]["id_column"]
    create_id_index_if_not_exists(
        table_name=table_name,
        index_name=f"idx_{table_name}_{id_column}",
        column=id_column,
    )


def ingest_to_postgis(
    gdf: gpd.GeoDataFrame,
    table_name: str = "geometries_gadm",
    chunk_size: int = 10000,
) -> None:
    """Ingest the GeoDataFrame to PostGIS database in chunks."""
    from src.core.config import settings

    database_url = settings.get_database_url_for_psycopg2()
    engine = create_engine(database_url)

    gdf_copy = gdf.copy()
    gdf_copy["geometry"] = gpd.GeoSeries.from_wkb(gdf_copy["geometry"])

    total_records = len(gdf_copy)
    logger.info("Ingesting", records=total_records, chunk_size=chunk_size)

    # Process in chunks
    for i in range(0, total_records, chunk_size):
        chunk = gdf_copy.iloc[i : i + chunk_size]
        if_exists_param = "replace" if i == 0 else "append"

        chunk.to_postgis(
            table_name, engine, if_exists=if_exists_param, index=False
        )

        records_processed = min(i + chunk_size, total_records)
        logger.info("Processed chunk", records=records_processed, total=total_records)

    logger.info("Ingested to PostGIS", table=table_name, records=total_records)


def main():
    """Main function to download, extract, and ingest GADM data."""
    # Download and extract GADM data
    zip_path = download(GADM_ZIP_URL, "data/gadm_410-levels.zip")
    gpkg_path = extract_gpkg(Path(zip_path), Path("data"))

    logger.info("Ingesting GADM data to PostGIS in chunks")
    ingest_gadm_chunked(gpkg_path)
    logger.info("GADM ingestion completed successfully")


if __name__ == "__main__":
    main()
