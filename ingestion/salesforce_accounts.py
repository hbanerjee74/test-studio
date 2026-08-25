#!/usr/bin/env python3
"""Pipeline to load Salesforce accounts data."""
import dlt
from salesforce import salesforce_source


def load_accounts() -> None:
    """Execute a pipeline to ingest Salesforce accounts."""
    pipeline = dlt.pipeline(
        pipeline_name="salesforce_accounts",
        destination="duckdb",
        dataset_name="salesforce_accounts",
    )
    load_info = pipeline.run(salesforce_source().account)
    print(load_info)


if __name__ == "__main__":
    load_accounts()