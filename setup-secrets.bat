@echo off
REM ======================================
REM Teams Sprint Bot - GCP Secret Manager Setup
REM Reads values from .env and stores them as secrets
REM Run this ONCE before first deploy (or when secrets change)
REM ======================================

setlocal EnableDelayedExpansion

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

if "%GOOGLE_PROJECT_ID%"=="" (
    echo ERROR: GOOGLE_PROJECT_ID not found in .env
    exit /b 1
)

echo Using GCP Project: %GOOGLE_PROJECT_ID%
echo.

REM Enable Secret Manager API
echo [1/3] Enabling Secret Manager API...
call gcloud services enable secretmanager.googleapis.com --project=%GOOGLE_PROJECT_ID%

echo.
echo [2/3] Creating/updating secrets from .env values...
echo.

REM Define all secret names
set SECRETS=GEMINI_API_KEY MICROSOFT_APP_ID MICROSOFT_APP_PASSWORD MICROSOFT_TENANT_ID MONGODB_URL AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY ACS_CONNECTION_STRING AZURE_COGNITIVE_SERVICES_ENDPOINT

for %%S in (%SECRETS%) do (
    set "VAL=!%%S!"
    if not "!VAL!"=="" (
        echo   %%S ...
        echo !VAL!| gcloud secrets create %%S --data-file=- --project=%GOOGLE_PROJECT_ID% 2>nul || (
            echo     ^(exists, adding new version^)
            echo !VAL!| gcloud secrets versions add %%S --data-file=- --project=%GOOGLE_PROJECT_ID%
        )
    ) else (
        echo   %%S ... SKIPPED ^(empty in .env^)
    )
)

echo.
echo [3/3] Granting Cloud Run service account access to secrets...

REM Get the project number for the default compute service account
for /f %%i in ('gcloud projects describe %GOOGLE_PROJECT_ID% --format^="value(projectNumber)"') do set PROJECT_NUMBER=%%i
set SA=%PROJECT_NUMBER%-compute@developer.gserviceaccount.com

echo   Service account: %SA%

for %%S in (%SECRETS%) do (
    set "VAL=!%%S!"
    if not "!VAL!"=="" (
        gcloud secrets add-iam-policy-binding %%S ^
            --member="serviceAccount:%SA%" ^
            --role="roles/secretmanager.secretAccessor" ^
            --project=%GOOGLE_PROJECT_ID% >nul 2>&1
        echo   %%S ... granted
    )
)

echo.
echo === Secret Manager Setup Complete ===
echo.
echo Secrets stored: %SECRETS%
echo Service account %SA% has accessor role on all secrets.
echo.
echo Now run: deploy.bat
echo.

endlocal
