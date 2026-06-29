import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def upload_raw_data():
    print("=== UPLOADING RAW DATA TO S3 ===\n")
    
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )
    
    bucket = os.getenv('S3_BUCKET')
    raw_data_path = 'data/raw/'
    
    files = os.listdir(raw_data_path)
    csv_files = [f for f in files if f.endswith('.csv')]
    
    print(f"Found {len(csv_files)} CSV files to upload\n")
    
    for filename in csv_files:
        filepath = os.path.join(raw_data_path, filename)
        s3_key = f'raw/{filename}'
        
        s3.upload_file(filepath, bucket, s3_key)
        print(f"✅ Uploaded: {filename}")
    
    print(f"\n=== DONE: {len(csv_files)} files uploaded to S3 ===")

if __name__ == '__main__':
    upload_raw_data()