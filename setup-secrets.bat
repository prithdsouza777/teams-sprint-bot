@echo off
REM ======================================
REM Create GCP Secret Manager Secrets
REM ======================================

SET PROJECT_ID=your-gcp-project-id

echo Creating secrets in GCP Secret Manager...
echo You will be prompted to enter each secret value.

echo.
echo [1/6] Microsoft App ID
call gcloud secrets create microsoft-app-id --project=%PROJECT_ID%
echo Enter your Microsoft App ID: 
set /p APP_ID=
echo %APP_ID% | gcloud secrets versions add microsoft-app-id --data-file=-

echo.
echo [2/6] Microsoft App Password
call gcloud secrets create microsoft-app-password --project=%PROJECT_ID%
echo Enter your Microsoft App Password:
set /p APP_PASS=
echo %APP_PASS% | gcloud secrets versions add microsoft-app-password --data-file=-

echo.
echo [3/6] Gemini API Key
call gcloud secrets create gemini-api-key --project=%PROJECT_ID%
echo Enter your Gemini API Key:
set /p GEMINI=
echo %GEMINI% | gcloud secrets versions add gemini-api-key --data-file=-

echo.
echo [4/6] MongoDB Database URL
call gcloud secrets create database-url --project=%PROJECT_ID%
echo Enter your MongoDB Connection String:
set /p DBURL=
echo %DBURL% | gcloud secrets versions add database-url --data-file=-

echo.
echo [5/6] AWS Access Key ID
call gcloud secrets create aws-access-key --project=%PROJECT_ID%
echo Enter your AWS Access Key ID:
set /p AWSKEY=
echo %AWSKEY% | gcloud secrets versions add aws-access-key --data-file=-

echo.
echo [6/6] AWS Secret Access Key
call gcloud secrets create aws-secret-key --project=%PROJECT_ID%
echo Enter your AWS Secret Access Key:
set /p AWSSECRET=
echo %AWSSECRET% | gcloud secrets versions add aws-secret-key --data-file=-

echo.
echo ========================================
echo All secrets created!
echo ========================================
