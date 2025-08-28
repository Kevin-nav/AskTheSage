import os
import boto3
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Get credentials from environment
bucket_name = os.getenv("S3_BUCKET_NAME")
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")

# Check if variables are loaded
if not all([bucket_name, aws_access_key_id, aws_secret_access_key, aws_region]):
    logging.error("One or more required environment variables are missing.")
    exit(1)

logging.info(f"Attempting to connect to S3 bucket: {bucket_name} in region: {aws_region}")

# Create a client
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )
    
    # Create a dummy file to upload
    file_content = "This is a test file from Gemini."
    file_name = "gemini_s3_test.txt"
    s3_key = f"test-uploads/{file_name}"

    logging.info(f"Uploading '{file_name}' to s3://{bucket_name}/{s3_key}")

    # Upload the file
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=file_content,
        ContentType='text/plain'
    )

    logging.info("\033[92mSuccess! File uploaded to S3 successfully.\033[0m")
    logging.info("This confirms your credentials and permissions for writing to the bucket are correct.")

except Exception as e:
    logging.error(f"\033[91mS3 Connection Failed: {e}\033[0m", exc_info=True)

