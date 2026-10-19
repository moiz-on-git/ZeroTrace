"""Inventory endpoint — schema + PII classification of all tables."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import require_service_key
from src.api.schemas import ApiResponse, ColumnInfo, InventoryResponse, TableInfo
from src.seed.iceberg_writer import TABLE_PII_COLS, TABLE_SCHEMAS, TABLE_TAGS

router = APIRouter()

# Column type hints (simplified — all columns are STRING in our Iceberg schema)
_TYPE_MAP = {
    "principal_inr": "DOUBLE",
    "interest_rate_pct": "DOUBLE",
    "amount_inr": "DOUBLE",
    "tenure_months": "INT",
    "duration_seconds": "INT",
    "opened": "BOOLEAN",
    "clicked": "BOOLEAN",
}


@router.get("/v1/inventory", dependencies=[Depends(require_service_key)])
async def get_inventory():
    tables = []
    for table_name, schema_cols in TABLE_SCHEMAS.items():
        pii_cols = TABLE_PII_COLS.get(table_name, [])
        cols = []
        for col_def in schema_cols:
            parts = col_def.strip().split()
            col_name = parts[0]
            col_type = parts[1] if len(parts) > 1 else "STRING"
            col_type = _TYPE_MAP.get(col_name, col_type)
            cols.append(ColumnInfo(
                name=col_name,
                type=col_type,
                is_pii=col_name in pii_cols,
            ))
        tables.append(TableInfo(
            name=table_name,
            layer="iceberg",
            tags=TABLE_TAGS.get(table_name, []),
            columns=cols,
            pii_columns=pii_cols,
        ))

    resp = InventoryResponse(
        tables=tables,
        vector_namespaces=["embeddings"],
        cache_keyspaces=["zt:cache:*"],
    )
    return ApiResponse(data=resp.model_dump())
