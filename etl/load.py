import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    """Create connection to PostgreSQL on AWS RDS"""
    host = os.getenv('RDS_HOST')
    port = os.getenv('RDS_PORT', '5432')
    database = os.getenv('RDS_DATABASE')
    user = os.getenv('RDS_USER')
    password = os.getenv('RDS_PASSWORD')
    
    connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'
    engine = create_engine(connection_string)
    return engine

def test_connection():
    """Test database connection before loading"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def load_table(df, table_name, engine):
    """Load a single DataFrame into PostgreSQL"""
    try:
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists='replace',
            index=False,
            chunksize=1000
        )
        print(f"✅ Loaded {table_name}: {len(df):,} rows")
    except Exception as e:
        print(f"❌ Failed to load {table_name}: {e}")

def load_all(transformed_tables):
    """Load all transformed tables into data warehouse"""
    print("=== LOADING DATA TO AWS RDS ===\n")
    
    # Test connection first
    if not test_connection():
        raise Exception("Cannot connect to database — check your .env credentials")
    
    engine = get_engine()
    print()
    
    # Load each table
    for table_name, df in transformed_tables.items():
        load_table(df, table_name, engine)
    
    print(f"\n=== LOAD COMPLETE: {len(transformed_tables)} tables loaded to PostgreSQL ===")

def verify_load(transformed_tables):
    """Verify row counts match after loading"""
    print("\n=== VERIFYING ROW COUNTS ===\n")
    engine = get_engine()
    
    all_match = True
    for table_name, df in transformed_tables.items():
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT COUNT(*) FROM {table_name}'))
            db_count = result.scalar()
        
        local_count = len(df)
        match = "✅" if db_count == local_count else "❌"
        print(f"{match} {table_name}: local={local_count:,} | database={db_count:,}")
        
        if db_count != local_count:
            all_match = False
    
    if all_match:
        print("\n✅ All row counts match — data loaded successfully")
    else:
        print("\n❌ Some tables have mismatched counts — check errors above")

if __name__ == '__main__':
    from extract import extract_all
    from validate import validate_all
    from transform import transform_all
    
    # Run full pipeline
    tables = extract_all()
    print()
    validate_all(tables)
    print()
    transformed = transform_all(tables)
    print()
    load_all(transformed)
    verify_load(transformed)