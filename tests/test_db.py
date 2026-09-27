# from scripts.db_utils import get_engine
# from sqlalchemy import text

# try:
#     engine = get_engine()

#     with engine.connect() as conn:
#         result = conn.execute(text("SELECT version();"))
#         print("✅ Database connection successful!")
#         print(result.fetchone()[0])

# except Exception as e:
#     print("❌ Database connection failed:")
#     print(type(e).__name__)
#     print(e)

# from sqlalchemy import text
# from scripts.db_utils import get_engine


# def test_database_connection():
#     engine = get_engine()

#     with engine.connect() as conn:
#         result = conn.execute(text("SELECT version();"))
#         version = result.fetchone()[0]

#         print(f"Connected to: {version}")

# from sqlalchemy import text
# from scripts.db_utils import get_engine


# def test_upcloud_tables():
#     engine = get_engine()

#     with engine.connect() as conn:
#         result = conn.execute(text("""
#             SELECT
#                 table_schema,
#                 table_name
#             FROM information_schema.tables
#             WHERE table_type = 'BASE TABLE'
#               AND table_schema NOT IN ('pg_catalog', 'information_schema')
#             ORDER BY table_schema, table_name;
#         """))

#         print("\n=== TABLES CURRENTLY ON UPCLOUD ===")

#         rows = result.fetchall()

#         for schema, table in rows:
#             print(f"{schema}.{table}")

#         print(f"\nTotal tables: {len(rows)}")

# from sqlalchemy import text
# from scripts.db_utils import get_engine


# def test_upcloud_schema():
#     engine = get_engine()

#     with engine.connect() as conn:
#         result = conn.execute(text("""
#             SELECT schema_name
#             FROM information_schema.schemata
#             WHERE schema_name = 'planting_schema_warehouse';
#         """))

#         schemas = result.fetchall()

#         print("\n=== UPCLOUD SCHEMA CHECK ===")

#         if schemas:
#             print("planting_schema_warehouse EXISTS")
#         else:
#             print("planting_schema_warehouse DOES NOT EXIST")

# from sqlalchemy import create_engine, text


# LOCAL_DB = "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"

# engine = create_engine(LOCAL_DB)

# with engine.connect() as conn:
#     result = conn.execute(text("""
#         SELECT
#             table_schema,
#             table_name
#         FROM information_schema.tables
#         WHERE table_type = 'BASE TABLE'
#           AND table_schema NOT IN ('pg_catalog', 'information_schema')
#         ORDER BY table_schema, table_name;
#     """))

#     rows = result.fetchall()

#     print("\n=== LOCAL DATABASE BASELINE ===")

#     for schema, table in rows:
#         print(f"{schema}.{table}")

#     print(f"\nTotal tables: {len(rows)}")

from sqlalchemy import create_engine, text

LOCAL_DB = "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"

engine = create_engine(LOCAL_DB)

with engine.connect() as conn:

    tables = conn.execute(text("""
        SELECT
            table_schema,
            table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)).fetchall()

    print("\n=== FINAL LOCAL DATABASE INVENTORY ===")

    total_rows = 0

    for schema, table in tables:

        count = conn.execute(
            text(f'''
                SELECT COUNT(*)
                FROM "{schema}"."{table}"
            ''')
        ).scalar()

        total_rows += count

        print(f"{schema}.{table} → {count:,} rows")

    print("\n======================================")
    print(f"Total tables: {len(tables)}")
    print(f"Total rows:   {total_rows:,}")