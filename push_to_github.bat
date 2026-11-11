@echo off
title Push Blood Donor Finder to GitHub
color 0A
echo ========================================================
echo        Upload Blood Donor Finder to GitHub
echo ========================================================
echo.
cd /d "%~dp0"
if not exist "app.py" (
    cd /d "C:\Users\Rohit Singh\Desktop\blood_donor_finder"
)

echo Current folder: %CD%
echo.
echo --------------------------------------------------------
echo Please copy your GitHub repository URL from your browser:
echo Example: https://github.com/your-username/blood-donor-finder.git
echo --------------------------------------------------------
echo.
set /p REPO_URL="Paste your GitHub Repository URL here: "

if "%REPO_URL%"=="" (
    echo [ERROR] No URL entered.
    pause
    exit /b
)

echo.
echo [1/3] Setting remote origin...
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [2/3] Setting branch to main...
git branch -M main

echo [3/3] Uploading all files to GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  [SUCCESS] All files are now uploaded to GitHub!
    echo ========================================================
) else (
    echo.
    echo If this is an existing repo with files (like a README), try:
    echo git push -u origin main --force
    echo.
)

echo.
pause
