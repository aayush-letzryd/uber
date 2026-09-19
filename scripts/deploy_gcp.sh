#!/bin/bash
set -e

# ==============================================================================
# Google Cloud Run Job & Cloud Scheduler Deployment Script (Non-Working Hours: 4:00 AM IST)
# ==============================================================================

PROJECT_ID="letzryd-prod"
REGION="asia-south1"
SERVICE_NAME="uber-data-automation-job"
SCHEDULER_JOB_NAME="uber-daily-sync-scheduler"
IMAGE_NAME="asia-south1-docker.pkg.dev/${PROJECT_ID}/letzryd-apps/uber-pipeline:latest"

echo "1. Building Docker Container Image..."
docker build -t ${IMAGE_NAME} .

echo "2. Pushing to Google Artifact Registry..."
docker push ${IMAGE_NAME}

echo "3. Creating / Updating Cloud Run Job..."
gcloud run jobs deploy ${SERVICE_NAME} \
    --image=${IMAGE_NAME} \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --cpu=2 \
    --memory=2Gi \
    --max-retries=3 \
    --task-timeout=3600s \
    --set-env-vars=PGHOST=35.200.196.113,PGPORT=5432,PGDATABASE=postgres,PGUSER=postgres,SENDER_EMAIL=vendor_aayush@letzryd.com,RECIPIENT_EMAIL=vendor_aayush@letzryd.com \
    --set-secrets=PGPASSWORD=UBER_PG_PASSWORD:latest,UBER_CLIENT_ID=UBER_CLIENT_ID:latest,UBER_CLIENT_SECRET=UBER_CLIENT_SECRET:latest,APP_PASSWORD=UBER_APP_PASSWORD:latest

echo "4. Setting up Cloud Scheduler Trigger (Daily at 4:00 AM IST - Non-Working Hours)..."
gcloud scheduler jobs create http ${SCHEDULER_JOB_NAME} \
    --location=${REGION} \
    --schedule="0 4 * * *" \
    --time-zone="Asia/Kolkata" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="cloud-run-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project=${PROJECT_ID} \
    || gcloud scheduler jobs update http ${SCHEDULER_JOB_NAME} \
    --location=${REGION} \
    --schedule="0 4 * * *" \
    --time-zone="Asia/Kolkata" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="cloud-run-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project=${PROJECT_ID}

echo "Deployment completed successfully! Cloud Run Job scheduled daily at 4:00 AM IST."
