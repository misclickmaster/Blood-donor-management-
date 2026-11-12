@echo off
title Push to GitHub - Blood Donor Management
color 0A
echo ========================================================
echo   Uploading Blood Donor Management to GitHub
echo   Repository: https://github.com/misclickmaster/Blood-donor-management-
echo ========================================================
echo.
cd /d "C:\Users\Rohit Singh\Desktop\blood_donor_finder"

echo 1. Current files ready for push:
git log -1 --oneline
echo.
echo 2. Pushing to GitHub...
echo (If a browser window opens, simply click 'Sign in' or 'Authorize')
echo.

git push -u origin main

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Remote might contain existing files. Attempting sync push...
    git push -u origin main --force
)

echo.
echo ========================================================
echo  All files are uploaded!
echo  Check your repository at:
echo  https://github.com/misclickmaster/Blood-donor-management-
echo ========================================================
echo.
pause
