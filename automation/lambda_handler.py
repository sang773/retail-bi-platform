import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    """
    AWS Lambda function — runs ETL pipeline on a schedule
    Deploy this to Lambda and trigger with EventBridge (weekly)
    """
    print(f"Pipeline triggered at: {datetime.now()}")
    
    try:
        # In real deployment this would trigger your pipeline
        # For now it logs the event and returns success
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Pipeline triggered successfully',
                'timestamp': datetime.now().isoformat(),
                'event': str(event)
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }