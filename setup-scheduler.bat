@echo off
REM ======================================
REM Cloud Scheduler Setup for Daily Standups
REM ======================================

SET PROJECT_ID=your-gcp-project-id
SET REGION=us-central1
SET CLOUD_RUN_URL=https://scrum-bot-xxxxx-uc.a.run.app

echo Setting up Cloud Scheduler for daily standups...

REM Create the scheduler job (9:30 AM IST, Mon-Fri)
call gcloud scheduler jobs create http daily-standup ^
  --project=%PROJECT_ID% ^
  --location=%REGION% ^
  --schedule="30 9 * * 1-5" ^
  --uri="%CLOUD_RUN_URL%/api/scheduled-standup" ^
  --http-method=POST ^
  --time-zone="Asia/Kolkata" ^
  --description="Triggers daily standup at 9:30 AM IST"

echo.
echo ========================================
echo Cloud Scheduler job created!
echo Schedule: 9:30 AM IST, Monday-Friday
echo ========================================
echo.
echo To test manually, run:
echo gcloud scheduler jobs run daily-standup --location=%REGION%
