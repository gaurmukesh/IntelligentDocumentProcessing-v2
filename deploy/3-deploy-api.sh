#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Build FastAPI Docker image and deploy to Lightsail Container Service.
# Run from your LOCAL machine (project root directory).
#
# Prerequisites:
#   - AWS CLI configured
#   - .env.prod file filled in
#   - Docker running locally
#
# Usage:
#   cd /path/to/IntelligentDocumentProcessing
#   chmod +x deploy/3-deploy-api.sh && ./deploy/3-deploy-api.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

SERVICE_NAME="idp-api"
REGION="ap-south-1"
IMAGE_NAME="idp-fastapi"

echo "==> Loading environment from .env.prod..."
export $(grep -v '^#' .env.prod | xargs)

echo "==> Building FastAPI Docker image for linux/amd64..."
docker build --platform linux/amd64 -t "$IMAGE_NAME:latest" ./backend-fastapi

echo "==> Pushing image to Lightsail Container Service..."
aws lightsail push-container-image \
  --region "$REGION" \
  --service-name "$SERVICE_NAME" \
  --label "$IMAGE_NAME" \
  --image "$IMAGE_NAME:latest"

# Get the pushed image name (Lightsail assigns a version like :idp-api.idp-fastapi.X)
PUSHED_IMAGE=$(aws lightsail get-container-images \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query "containerImages[0].image" \
  --output text)

echo "==> Pushed image: $PUSHED_IMAGE"

echo "==> Creating container deployment..."
aws lightsail create-container-service-deployment \
  --no-cli-pager \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --containers "{
    \"fastapi\": {
      \"image\": \"$PUSHED_IMAGE\",
      \"environment\": {
        \"APP_ENV\": \"production\",
        \"OPENAI_API_KEY\": \"$OPENAI_API_KEY\",
        \"OPENAI_MODEL\": \"$OPENAI_MODEL\",
        \"DATABASE_URL\": \"$DATABASE_URL\",
        \"S3_ACCESS_KEY\": \"$S3_ACCESS_KEY\",
        \"S3_SECRET_KEY\": \"$S3_SECRET_KEY\",
        \"S3_REGION\": \"$S3_REGION\",
        \"S3_BUCKET_NAME\": \"$S3_BUCKET_NAME\",
        \"KAFKA_BOOTSTRAP_SERVERS\": \"$KAFKA_BOOTSTRAP_SERVERS\",
        \"QDRANT_HOST\": \"$QDRANT_HOST\",
        \"QDRANT_PORT\": \"$QDRANT_PORT\",
        \"ERP_BASE_URL\": \"$ERP_BASE_URL\"
      },
      \"ports\": {\"8000\": \"HTTP\"}
    }
  }" \
  --public-endpoint "{
    \"containerName\": \"fastapi\",
    \"containerPort\": 8000,
    \"healthCheck\": {
      \"path\": \"/health\",
      \"intervalSeconds\": 30,
      \"timeoutSeconds\": 10,
      \"successCodes\": \"200\",
      \"unhealthyThreshold\": 5,
      \"healthyThreshold\": 2
    }
  }"

echo ""
echo "==> Deployment triggered! Checking status..."
sleep 10
aws lightsail get-container-services \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query "containerServices[0].{State:state, URL:url}" \
  --output table

echo ""
echo "✓ FastAPI deployed. The public URL is shown above."
echo "  Health check: <url>/health"
