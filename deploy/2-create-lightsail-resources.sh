#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Run this from your LOCAL machine.
# Creates Lightsail managed resources using AWS CLI.
#
# Prerequisites:
#   aws configure   (set your AWS credentials + region ap-south-1)
#
# Usage:
#   chmod +x 2-create-lightsail-resources.sh && ./2-create-lightsail-resources.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

REGION="ap-south-1"
DB_NAME="idp-database"
BUCKET_UPLOADS="idp-uploads"
BUCKET_FRONTEND="idp-frontend"
CONTAINER_SERVICE="idp-api"

echo "==> Creating Lightsail Managed PostgreSQL Database..."
aws lightsail create-relational-database \
  --relational-database-name "$DB_NAME" \
  --relational-database-blueprint-id postgres_14 \
  --relational-database-bundle-id micro_2_0 \
  --master-database-name idp \
  --master-username dbmasteruser \
  --region "$REGION"

echo ""
echo "==> Creating Lightsail Object Storage Buckets..."

# Bucket for uploaded documents
aws lightsail create-bucket \
  --bucket-name "$BUCKET_UPLOADS" \
  --bundle-id small_1_0 \
  --region "$REGION"

# Bucket for React static frontend (enable static website hosting)
aws lightsail create-bucket \
  --bucket-name "$BUCKET_FRONTEND" \
  --bundle-id small_1_0 \
  --region "$REGION"

echo ""
echo "==> Creating Lightsail Container Service (micro) for FastAPI..."
aws lightsail create-container-service \
  --service-name "$CONTAINER_SERVICE" \
  --power micro \
  --scale 1 \
  --region "$REGION"

echo ""
echo "========================================================"
echo "  Resources created! Next steps:"
echo "========================================================"
echo ""
echo "1. Get the database endpoint:"
echo "   aws lightsail get-relational-database --relational-database-name $DB_NAME --query 'relationalDatabase.masterEndpoint'"
echo ""
echo "2. Get Object Storage access keys:"
echo "   aws lightsail create-bucket-access-key --bucket-name $BUCKET_UPLOADS"
echo ""
echo "3. Update your .env.prod with the above values."
echo ""
echo "4. Get the Container Service endpoint after deployment:"
echo "   aws lightsail get-container-services --service-name $CONTAINER_SERVICE"
