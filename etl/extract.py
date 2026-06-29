import pandas as pd
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )

def extract_from_s3(filename):
    """Download a single CSV from S3 and return as DataFrame"""
    s3 = get_s3_client()
    bucket = os.getenv('S3_BUCKET')
    
    obj = s3.get_object(Bucket=bucket, Key=f'raw/{filename}')
    df = pd.read_csv(obj['Body'])
    print(f"✅ Extracted {filename}: {df.shape[0]:,} rows, {df.shape[1]} columns")
    return df

def extract_all():
    """Extract all 8 tables from S3"""
    print("=== EXTRACTING DATA FROM S3 ===\n")
    
    tables = {
        'orders': extract_from_s3('olist_orders_dataset.csv'),
        'order_items': extract_from_s3('olist_order_items_dataset.csv'),
        'customers': extract_from_s3('olist_customers_dataset.csv'),
        'products': extract_from_s3('olist_products_dataset.csv'),
        'sellers': extract_from_s3('olist_sellers_dataset.csv'),
        'payments': extract_from_s3('olist_order_payments_dataset.csv'),
        'reviews': extract_from_s3('olist_order_reviews_dataset.csv'),
        'geolocation': extract_from_s3('olist_geolocation_dataset.csv')
    }
    
    print(f"\n=== EXTRACTION COMPLETE: {len(tables)} tables loaded ===")
    return tables

if __name__ == '__main__':
    tables = extract_all()
    print("\nTable shapes:")
    for name, df in tables.items():
        print(f"  {name}: {df.shape}")