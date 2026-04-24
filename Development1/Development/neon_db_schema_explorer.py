
import psycopg2
import pandas as pd

_config = load_asset("Neon_Database")
_v = _config.value

# Extract endpoint ID from host URL (first part before first dot)
_host = _v['host_url']
_endpoint_id = _host.split('.')[0]  # e.g. 'ep-long-frog-ammcrhfw-pooler'
print("Endpoint ID:", _endpoint_id)

_conn = psycopg2.connect(
    host=_host,
    port=_v['port'],
    dbname=_v['database_name'],
    user=_v['username'],
    password=_v['password'],
    sslmode='require',
    options=f'endpoint={_endpoint_id}'
)

# List schemas
schemas_df = pd.read_sql("""
    SELECT schema_name 
    FROM information_schema.schemata 
    WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    ORDER BY schema_name
""", _conn)

print("=== SCHEMAS ===")
print(schemas_df.to_string())

# List all tables 
tables_df = pd.read_sql("""
    SELECT 
        t.table_schema,
        t.table_name,
        t.table_type
    FROM information_schema.tables t
    WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    ORDER BY t.table_schema, t.table_name
""", _conn)

print("\n=== TABLES ===")
print(tables_df.to_string())

_conn.close()
