#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Build React app and upload to Lightsail Object Storage (static site).
# Run from your LOCAL machine (project root directory).
#
# Prerequisites:
#   - Node.js installed  (brew install node)
#   - AWS CLI configured
#   - VITE_FASTAPI_URL set to your Lightsail Container Service URL
#
# Usage:
#   cd /path/to/IntelligentDocumentProcessing
#   chmod +x deploy/4-deploy-frontend.sh && ./deploy/4-deploy-frontend.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

BUCKET_FRONTEND="idp-frontend"
REGION="ap-south-1"

# Get the Container Service URL
FASTAPI_URL=$(aws lightsail get-container-services \
  --service-name "idp-api" \
  --region "$REGION" \
  --query "containerServices[0].url" \
  --output text)

echo "==> FastAPI URL: $FASTAPI_URL"

echo "==> Building React app..."
cd frontend-react
VITE_FASTAPI_URL="$FASTAPI_URL" npm run build

echo "==> Uploading React build to Lightsail Object Storage..."
aws s3 sync dist/ "s3://$BUCKET_FRONTEND/" \
  --region "$REGION" \
  --delete \
  --cache-control "public, max-age=31536000" \
  --exclude "index.html"

# index.html must NOT be cached (so deploys take effect immediately)
aws s3 cp dist/index.html "s3://$BUCKET_FRONTEND/index.html" \
  --region "$REGION" \
  --cache-control "no-cache, no-store, must-revalidate"

echo ""
echo "✓ Frontend deployed to: https://$BUCKET_FRONTEND.s3-website.$REGION.amazonaws.com"
echo ""
echo "IMPORTANT: Enable static website hosting on the bucket in Lightsail console:"
echo "  Lightsail → Storage → $BUCKET_FRONTEND → Properties → Static website hosting"
echo "  Set index document: index.html"
echo "  Set error document: index.html  (for React Router to work)"
