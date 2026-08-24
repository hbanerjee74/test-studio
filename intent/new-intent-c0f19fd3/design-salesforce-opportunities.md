# Salesforce Opportunities Ingestion Pipeline

## Scope
- Artifact: `salesforce_opportunities_pipeline.py`
- Source: Salesforce (Opportunity object)
- Mapping: `salesforce.Opportunity` -> bronze `salesforce_opportunities`

## Grain
- One row per Salesforce Opportunity ID.

## Decisions
1. **Initial data load approach**:
   - The Salesforce source is not currently configured in `ingestion/.dlt/config.toml`. A configuration step will be needed before schema discovery can happen.
   - We will use an add-or-update-source operation to define the connection and its secret credentials, then discover the schema for `Opportunity`, and subsequently generate the pipeline code to load into the ephemeral target.
2. **Schema Contract strategy**:
   - We'll enforce a strict schema contract during extraction (e.g. `schema_contract="evolve"`) to capture changes to `Opportunity` fields over time, which are frequent in Salesforce instances.
3. **Data history and SCD**:
   - Given the SLA is Daily, a daily snapshot or incremental load based on `SystemModstamp` is appropriate. We recommend an incremental load using the standard dlt Salesforce verified source, tracking changes with `SystemModstamp` to efficiently handle high data volumes, appending or merging appropriately. (See `docs/adr/0001-salesforce-incremental-load-strategy.md`)


## Unresolved Open Questions
- None.

## History
- **2026-08-24**: Initial pipeline design for Opportunities data.
