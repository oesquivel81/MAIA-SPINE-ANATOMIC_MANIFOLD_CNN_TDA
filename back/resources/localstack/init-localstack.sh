#!/bin/bash
# LocalStack initialization script for S3

echo "Initializing LocalStack S3..."

# Wait for LocalStack to be ready
sleep 5

# Create S3 bucket
awslocal s3 mb s3://project-files --region us-east-1

# Enable versioning on the bucket
awslocal s3api put-bucket-versioning \
  --bucket project-files \
  --versioning-configuration Status=Enabled \
  --region us-east-1

# Enable server-side encryption (AES256)
awslocal s3api put-bucket-encryption \
  --bucket project-files \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --region us-east-1

# Block public access
awslocal s3api put-public-access-block \
  --bucket project-files \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region us-east-1

echo "✓ LocalStack S3 bucket 'project-files' created with versioning and encryption"
