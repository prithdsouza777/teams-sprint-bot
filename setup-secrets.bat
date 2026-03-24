@echo off
REM Setup secrets in GCP Secret Manager for Teams Sprint Bot
REM Run this BEFORE deploying to Cloud Run

setlocal

set PROJECT_ID=YOUR_GCP_PROJECT_ID

echo.
echo === Setting up GCP Secrets for Teams Sprint Bot ===
echo.

REM Check PROJECT_ID
if "%PROJECT_ID%"=="YOUR_GCP_PROJECT_ID" (
    echo ERROR: Please edit this script and set PROJECT_ID
    exit /b 1
)

echo [1/6] Enabling Secret Manager API...
call gcloud services enable secretmanager.googleapis.com --project=%PROJECT_ID%

echo.
echo You will be prompted to enter each secret value.
echo.

REM Create secrets (will prompt for values)
echo [2/6] Creating GEMINI_API_KEY secret...
echo Enter your Gemini API Key:
set /p GEMINI_KEY=
echo %GEMINI_KEY%| gcloud secrets create GEMINI_API_KEY --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %GEMINI_KEY%| gcloud secrets versions add GEMINI_API_KEY --data-file=- --project=%PROJECT_ID%
)

echo.
echo [3/6] Creating MICROSOFT_APP_ID secret...
echo Enter your Microsoft App ID:
set /p MS_APP_ID=
echo %MS_APP_ID%| gcloud secrets create MICROSOFT_APP_ID --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %MS_APP_ID%| gcloud secrets versions add MICROSOFT_APP_ID --data-file=- --project=%PROJECT_ID%
)

echo.
echo [4/6] Creating MICROSOFT_APP_PASSWORD secret...
echo Enter your Microsoft App Password:
set /p MS_APP_PWD=
echo %MS_APP_PWD%| gcloud secrets create MICROSOFT_APP_PASSWORD --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %MS_APP_PWD%| gcloud secrets versions add MICROSOFT_APP_PASSWORD --data-file=- --project=%PROJECT_ID%
)

echo.
echo [5/6] Creating MONGODB_URL secret...
echo Enter your MongoDB URL:
set /p MONGO_URL=
echo %MONGO_URL%| gcloud secrets create MONGODB_URL --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %MONGO_URL%| gcloud secrets versions add MONGODB_URL --data-file=- --project=%PROJECT_ID%
)

echo.
echo [6/6] Creating AWS secrets...
echo Enter AWS Access Key ID:
set /p AWS_KEY=
echo %AWS_KEY%| gcloud secrets create AWS_ACCESS_KEY_ID --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %AWS_KEY%| gcloud secrets versions add AWS_ACCESS_KEY_ID --data-file=- --project=%PROJECT_ID%
)

echo Enter AWS Secret Access Key:
set /p AWS_SECRET=
echo %AWS_SECRET%| gcloud secrets create AWS_SECRET_ACCESS_KEY --data-file=- --project=%PROJECT_ID% 2>nul || (
    echo Updating existing secret...
    echo %AWS_SECRET%| gcloud secrets versions add AWS_SECRET_ACCESS_KEY --data-file=- --project=%PROJECT_ID%
)

echo.
echo === Secrets Setup Complete! ===
echo.
echo Now run: deploy-cloudrun.bat
echo.

endlocal
