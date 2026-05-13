#!/bin/sh
set -e

awslocal s3api create-bucket --bucket project-files --region us-east-1 || true
