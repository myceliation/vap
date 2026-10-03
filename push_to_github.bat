@echo off
setlocal EnableExtensions
rem ==========================================================================
rem  push_to_github.bat  -  publish this folder to github.com/myceliation/vap
rem  and turn on GitHub Pages at https://myceliation.github.io/vap/
rem
rem  First run: installs Git and the GitHub CLI if missing (via winget), opens
rem  a browser once so you can log in to GitHub, creates the repo, pushes, and
rem  enables Pages. Later runs: commits whatever changed and pushes.
rem  Raw OPRA files in data\raw\ are never uploaded (see .gitignore).
rem ==========================================================================
set "OWNER=myceliation"
set "REPO=vap"
cd /d "%~dp0"
title Publishing %OWNER%/%REPO%

rem ---- tools ---------------------------------------------------------------
where git >nul 2>&1 || (
  echo Git not found. Installing Git for Windows...
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  set "PATH=%PATH%;%ProgramFiles%\Git\cmd"
)
where gh >nul 2>&1 || (
  echo GitHub CLI not found. Installing it...
  winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
  set "PATH=%PATH%;%ProgramFiles%\GitHub CLI"
)
where git >nul 2>&1 || (echo Git still isn't on PATH. Close this window and run the script again. & goto :fail)
where gh  >nul 2>&1 || (echo GitHub CLI still isn't on PATH. Close this window and run the script again. & goto :fail)

rem ---- login (once) --------------------------------------------------------
gh auth status --hostname github.com >nul 2>&1 || (
  echo.
  echo A browser window will open. Log in to GitHub as %OWNER% and paste the code shown here.
  gh auth login --hostname github.com --git-protocol https --web || goto :fail
)
gh auth setup-git >nul 2>&1

rem ---- repo housekeeping ---------------------------------------------------
set "HERE=%CD:\=/%"
git config --global --get-all safe.directory | findstr /x /c:"%HERE%" >nul 2>&1 || git config --global --add safe.directory "%HERE%"
if not exist ".git" git init -b main
if exist ".git\index.lock" del /f /q ".git\index.lock"
git config core.fileMode false
git config core.autocrlf false
for /f "delims=" %%L in ('gh api user --jq .login') do set "GHLOGIN=%%L"
for /f "delims=" %%I in ('gh api user --jq .id') do set "GHID=%%I"
git config user.name  >nul 2>&1 || git config user.name "%GHLOGIN%"
git config user.email >nul 2>&1 || git config user.email "%GHID%+%GHLOGIN%@users.noreply.github.com"
git branch -M main

rem ---- commit --------------------------------------------------------------
git add -A
git diff --cached --quiet && (echo Nothing new to commit.) || (
  git commit -q -m "Update archive (%DATE%)" || goto :fail
  echo Committed changes.
)

rem ---- create the GitHub repo if needed and push ---------------------------
gh repo view %OWNER%/%REPO% >nul 2>&1 || (
  echo Creating github.com/%OWNER%/%REPO% ...
  gh repo create %OWNER%/%REPO% --public --description "Archived NJ vacant and abandoned property records from OPRA requests 2025-26 and other abandoned places, on a map" || goto :fail
)
git remote get-url origin >nul 2>&1 || git remote add origin https://github.com/%OWNER%/%REPO%.git
git remote set-url origin https://github.com/%OWNER%/%REPO%.git
git push -u origin main || goto :fail

rem ---- GitHub Pages --------------------------------------------------------
gh api repos/%OWNER%/%REPO%/pages >nul 2>&1 || (
  echo Turning on GitHub Pages...
  gh api -X POST repos/%OWNER%/%REPO%/pages -f "source[branch]=main" -f "source[path]=/" >nul || goto :fail
)

echo.
echo Done. The page lives at https://%OWNER%.github.io/%REPO%/
echo The first build takes a minute or two; refresh if it 404s.
start "" "https://%OWNER%.github.io/%REPO%/"
echo.
echo To freeze it later: repo Settings, General, "Archive this repository".
pause
exit /b 0

:fail
echo.
echo Something went wrong above. Nothing on your PC was deleted; fix the
echo message shown and run this script again - it picks up where it stopped.
pause
exit /b 1
