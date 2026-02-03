@echo off
REM ======================================
REM AI Scrum Bot - GCP Deployment Script
REM ======================================

SET PROJECT_ID=your-gcp-project-id
SET REGION=us-central1
SET SERVICE_NAME=scrum-bot

echo [1/4] Setting GCP project...
call gcloud config set project %PROJECT_ID%

echo [2/4] Building and pushing Docker image...
call gcloud builds submit --tag gcr.io/%PROJECT_ID%/%SERVICE_NAME%

echo [3/4] Deploying to Cloud Run...
call gcloud run deploy %SERVICE_NAME% ^
  --image gcr.io/%PROJECT_ID%/%SERVICE_NAME% ^
  --platform managed ^
  --region %REGION% ^
  --allow-unauthenticated ^
  --set-env-vars "NODE_ENV=production" ^
  --set-secrets "MICROSOFT_APP_ID=microsoft-app-id:latest,MICROSOFT_APP_PASSWORD=microsoft-app-password:latest,GEMINI_API_KEY=gemini-api-key:latest,DATABASE_URL=database-url:latest,AWS_ACCESS_KEY_ID=aws-access-key:latest,AWS_SECRET_ACCESS_KEY=aws-secret-key:latest"

echo [4/4] Getting service URL...
call gcloud run services describe %SERVICE_NAME% --region %REGION% --format="value(status.url)"

echo.
echo ========================================
echo Deployment complete!
echo Update your Azure Bot registration with the URL above + /api/messages
echo ========================================
