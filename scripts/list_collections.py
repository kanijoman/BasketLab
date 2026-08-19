#!/usr/bin/env python3
"""List all collections in the database."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.database.connection import MongoDBConnection

conn = MongoDBConnection()
if conn.is_connected():
    db = conn.get_database()
    collections = sorted(db.list_collection_names())
    print(f"\n📦 Available Collections ({len(collections)}):\n")
    for col in collections:
        col_obj = db[col]
        count = col_obj.count_documents({})
        print(f"  {col:40s} ({count:,} documents)")
    conn.close()
else:
    print("❌ Could not connect to MongoDB")
