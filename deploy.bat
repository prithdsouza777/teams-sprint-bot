@echo off
REM ======================================
REM AI Scrum Bot - GCP Deployment Script
REM Reads credentials from .env file
REM ======================================

setlocal EnableDelayedExpansion

SET REGION=us-central1
SET SERVICE_NAME=scrum-bot

echo.
echo === AI Scrum Bot - GCP Cloud Run Deployment ===
echo.

REM Load environment variables from .env file
echo Loading configuration from .env...
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    REM Skip comments and empty lines
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" if not "%%b"=="" (
            set "%%a=%%b"
        )
    )
)

REM Check if GOOGLE_PROJECT_ID is set
if "%GOOGLE_PROJECT_ID%"=="" (
    echo ERROR: GOOGLE_PROJECT_ID not found in .env
    echo Please add: GOOGLE_PROJECT_ID=your-project-id
    exit /b 1
)

echo Using GCP Project: %GOOGLE_PROJECT_ID%

echo.
echo [1/4] Setting GCP project...
call gcloud config set project %GOOGLE_PROJECT_ID%

echo.
echo [2/4] Enabling required APIs...
call gcloud services enable cloudbuild.googleapis.com run.googleapis.com

echo.
echo [3/4] Building Docker image...
call gcloud builds submit --tag gcr.io/%GOOGLE_PROJECT_ID%/%SERVICE_NAME%

echo.
echo [4/4] Deploying to Cloud Run...
REM Copy .env to container won't work, so we pass all env vars explicitly
REM Using --update-env-vars to set each one properly
call gcloud run deploy %SERVICE_NAME% ^
  --image gcr.io/%GOOGLE_PROJECT_ID%/%SERVICE_NAME% ^
  --platform managed ^
  --region %REGION% ^
  --allow-unauthenticated ^
  --memory 512Mi ^
  --timeout 300 ^
  --update-env-vars "GOOGLE_PROJECT_ID=%GOOGLE_PROJECT_ID%,GEMINI_API_KEY=%GEMINI_API_KEY%,MICROSOFT_APP_ID=%MICROSOFT_APP_ID%,MICROSOFT_APP_PASSWORD=%MICROSOFT_APP_PASSWORD%,MICROSOFT_TENANT_ID=%MICROSOFT_TENANT_ID%,MONGODB_URL=%MONGODB_URL%,AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%,AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%,AWS_REGION=%AWS_REGION%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Deployment failed! Check the logs above.
    exit /b 1
)

echo.
echo === Getting Service URL ===
for /f %%i in ('gcloud run services describe %SERVICE_NAME% --region %REGION% --format^="value(status.url)"') do set SERVICE_URL=%%i
echo.
echo ========================================
echo Deployment complete!
echo.
echo Service URL: %SERVICE_URL%
echo.
echo Next steps:
echo 1. Update Azure Bot messaging endpoint to:
echo    %SERVICE_URL%/api/messages
echo.
echo 2. Test the bot in Azure Web Chat
echo ========================================

endlocal
