import os
import io
import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# We support standard S3 environment variables (which work with Supabase)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION") or "auto"

# Fallback for Cloudflare R2 specific Account ID configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")

def get_s3_client():
    # Check if either S3 credentials or R2 credentials are set
    has_s3 = all([S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY])
    has_r2 = all([R2_ACCOUNT_ID, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY])
    
    if not (has_s3 or has_r2):
        print("Warning: Cloud Storage credentials are not fully configured in your .env file.")
        return None
        
    if S3_ENDPOINT_URL:
        endpoint_url = S3_ENDPOINT_URL
    else:
        endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        
    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION
    )

def upload_to_s3(file_obj, s3_key):
    client = get_s3_client()
    if not client:
        raise ValueError("Cloud Storage client is not configured. Check your .env file.")
    
    try:
        file_obj.seek(0)
    except:
        pass
        
    client.upload_fileobj(file_obj, S3_BUCKET_NAME, s3_key)
    print(f"Uploaded object to storage: {s3_key}")

def download_from_s3(s3_key):
    client = get_s3_client()
    if not client:
        raise ValueError("Cloud Storage client is not configured. Check your .env file.")
    
    buffer = io.BytesIO()
    client.download_fileobj(S3_BUCKET_NAME, s3_key, buffer)
    buffer.seek(0)
    return buffer

def copy_s3_object(src_key, dest_key):
    client = get_s3_client()
    if not client:
        raise ValueError("Cloud Storage client is not configured. Check your .env file.")
        
    copy_source = {
        'Bucket': S3_BUCKET_NAME,
        'Key': src_key
    }
    client.copy_object(
        CopySource=copy_source,
        Bucket=S3_BUCKET_NAME,
        Key=dest_key
    )
    print(f"Copied storage object from {src_key} to {dest_key}")

def delete_s3_object(s3_key):
    client = get_s3_client()
    if not client:
        print("Warning: Could not delete storage object, client not configured.")
        return
        
    client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
    print(f"Deleted storage object: {s3_key}")

def read_dataframe_from_s3(s3_key):
    buffer = download_from_s3(s3_key)
    return pd.read_csv(buffer)

def save_dataframe_to_s3(df, s3_key):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    bytes_buffer = io.BytesIO(buffer.getvalue().encode('utf-8'))
    upload_to_s3(bytes_buffer, s3_key)
