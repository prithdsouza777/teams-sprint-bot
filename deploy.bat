@echo off
REM ======================================
REM Teams Sprint Bot - Secure GCP Deployment
REM Secrets via Secret Manager, config via env vars
REM Run setup-secrets.bat first if secrets have changed
REM ======================================

setlocal EnableDelayedExpansion

SET REGION=us-central1
SET SERVICE_NAME=teams-sprint-bot

echo.
echo === Teams Sprint Bot - Secure GCP Cloud Run Deployment ===
echo.

REM Load environment variables from .env file
echo Loading configuration from .env...
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
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
echo [1/5] Setting GCP project...
call gcloud config set project %GOOGLE_PROJECT_ID%

echo.
echo [2/5] Enabling required APIs...
call gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com

echo.
echo [3/5] Verifying secrets exist in Secret Manager...
set MISSING_SECRETS=0
for %%S in (GEMINI_API_KEY MICROSOFT_APP_ID MICROSOFT_APP_PASSWORD MICROSOFT_TENANT_ID MONGODB_URL AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY ACS_CONNECTION_STRING AZURE_COGNITIVE_SERVICES_ENDPOINT) do (
    gcloud secrets describe %%S --project=%GOOGLE_PROJECT_ID% >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo   MISSING: %%S
        set MISSING_SECRETS=1
    )
)
if %MISSING_SECRETS%==1 (
    echo.
    echo ERROR: Some secrets are missing from Secret Manager.
    echo Run setup-secrets.bat first to create them.
    exit /b 1
)
echo   All secrets found.

echo.
echo [4/5] Building Docker image...
call gcloud builds submit --tag us-central1-docker.pkg.dev/%GOOGLE_PROJECT_ID%/cloud-run-source-deploy/%SERVICE_NAME%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed! Check the logs above.
    exit /b 1
)

echo.
echo [5/5] Deploying to Cloud Run (secrets via Secret Manager)...
call gcloud run deploy %SERVICE_NAME% ^
  --image us-central1-docker.pkg.dev/%GOOGLE_PROJECT_ID%/cloud-run-source-deploy/%SERVICE_NAME% ^
  --platform managed ^
  --region %REGION% ^
  --allow-unauthenticated ^
  --memory 512Mi ^
  --timeout 300 ^
  --update-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,MICROSOFT_APP_ID=MICROSOFT_APP_ID:latest,MICROSOFT_APP_PASSWORD=MICROSOFT_APP_PASSWORD:latest,MICROSOFT_TENANT_ID=MICROSOFT_TENANT_ID:latest,MONGODB_URL=MONGODB_URL:latest,AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID:latest,AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY:latest,ACS_CONNECTION_STRING=ACS_CONNECTION_STRING:latest,AZURE_COGNITIVE_SERVICES_ENDPOINT=AZURE_COGNITIVE_SERVICES_ENDPOINT:latest" ^
  --update-env-vars "GOOGLE_PROJECT_ID=%GOOGLE_PROJECT_ID%,AWS_REGION=%AWS_REGION%,ACS_CALLBACK_URL=%ACS_CALLBACK_URL%,VOICE_STANDUP_WAIT_SECONDS=%VOICE_STANDUP_WAIT_SECONDS%,VOICE_STANDUP_SILENCE_TIMEOUT=%VOICE_STANDUP_SILENCE_TIMEOUT%,VOICE_STANDUP_MAX_SILENCE_RETRIES=%VOICE_STANDUP_MAX_SILENCE_RETRIES%"

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
echo Secrets are managed via GCP Secret Manager (not plaintext env vars).
echo.
echo Next steps:
echo 1. Update Azure Bot messaging endpoint to:
echo    %SERVICE_URL%/api/messages
echo.
echo 2. Test the bot in Azure Web Chat
echo ========================================

endlocal
