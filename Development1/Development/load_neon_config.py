import psycopg2
import pandas as pd

_config = load_asset("Neon_Database")
print("Config keys:", list(_config.keys()) if isinstance(_config, dict) else type(_config))
print(_config)