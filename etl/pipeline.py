import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add etl folder to path
sys.path.append(os.path.dirname(__file__))

from extract import extract_all
from validate import validate_all
from transform import transform_all
from load import load_all, verify_load

def run_pipeline():
    start_time = datetime.now()
    print("=" * 50)
    print("   RETAIL BI PLATFORM — ETL PIPELINE")
    print(f"   Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        # Step 1: Extract
        print("\n[STEP 1/4] EXTRACTING DATA FROM S3...")
        tables = extract_all()
        
        # Step 2: Validate
        print("\n[STEP 2/4] VALIDATING DATA...")
        results = validate_all(tables)
        if not all(results.values()):
            raise Exception("Validation failed — pipeline stopped")
        
        # Step 3: Transform
        print("\n[STEP 3/4] TRANSFORMING DATA...")
        transformed = transform_all(tables)
        
        # Step 4: Load
        print("\n[STEP 4/4] LOADING TO DATABASE...")
        load_all(transformed)
        verify_load(transformed)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        print("\n" + "=" * 50)
        print("   PIPELINE COMPLETED SUCCESSFULLY")
        print(f"   Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration: {duration} seconds")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_pipeline()