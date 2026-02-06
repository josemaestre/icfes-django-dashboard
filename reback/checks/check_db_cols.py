
import os
import sys
import django
from pathlib import Path

# Setup paths
current_path = Path('c:\\proyectos\\www\\reback').resolve()
sys.path.append(str(current_path))
sys.path.append(str(current_path / "reback"))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.conf import settings
from icfes_dashboard.db_utils import execute_query

print(f"Using database: {settings.ICFES_DUCKDB_PATH}")

try:
    df_cluster = execute_query("SELECT * FROM gold.dim_colegios_cluster LIMIT 1")
    print("\nColumns in dim_colegios_cluster:")
    print(df_cluster.columns.tolist())
    print("\nData sample:")
    print(df_cluster.to_dict(orient='records'))

except Exception as e:
    print(f"Error: {e}")
