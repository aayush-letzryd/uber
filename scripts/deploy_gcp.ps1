# Google Cloud Run & Cloud Scheduler Deployment Script (PowerShell)
$PROJECT_ID = "letzryd-prod"
$REGION = "asia-south1"
$SERVICE_NAME = "uber-data-automation-job"
$SCHEDULER_JOB_NAME = "uber-daily-sync-scheduler"
$IMAGE_NAME = "asia-south1-docker.pkg.dev/$PROJECT_ID/letzryd-apps/uber-pipeline:latest"

Write-Host "1. Building Docker Container Image..."
docker build -t $IMAGE_NAME .

Write-Host "2. Pushing to Google Artifact Registry..."
docker push $IMAGE_NAME

Write-Host "3. Deploying Cloud Run Job..."
gcloud run jobs deploy $SERVICE_NAME `
    --image=$IMAGE_NAME `
    --region=$REGION `
    --project=$PROJECT_ID `
    --cpu=2 `
    --memory=2Gi `
    --max-retries=3 `
    --task-timeout=3600s

Write-Host "4. Setting up Cloud Scheduler (Daily at 4:00 AM IST)..."
gcloud scheduler jobs create http $SCHEDULER_JOB_NAME `
    --location=$REGION `
    --schedule="0 4 * * *" `
    --time-zone="Asia/Kolkata" `
    --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$SERVICE_NAME`:run" `
    --http-method=POST `
    --oauth-service-account-email="cloud-run-invoker@$PROJECT_ID.iam.gserviceaccount.com" `
    --project=$PROJECT_ID

Write-Host "Deployment completed successfully!"
