@echo off
REM Apagar todas as issues antigas do Radar de Guerra

set REPO=GilvanS/historico-clash-roayle

echo.
echo ============================================
echo  Apagando Issues Antigas
echo ============================================
echo.

echo [1] Apagando Issue 1...
gh api repos/%REPO%/issues/1 -X PATCH -f state=closed

echo [2] Apagando Issue 2...
gh api repos/%REPO%/issues/2 -X PATCH -f state=closed

echo [3] Apagando Issue 3...
gh api repos/%REPO%/issues/3 -X PATCH -f state=closed

echo [4] Apagando Issue 4...
gh api repos/%REPO%/issues/4 -X PATCH -f state=closed

echo [5] Apagando Issue 5...
gh api repos/%REPO%/issues/5 -X PATCH -f state=closed

echo [6] Apagando Issue 6...
gh api repos/%REPO%/issues/6 -X PATCH -f state=closed

echo [7] Apagando Issue 7...
gh api repos/%REPO%/issues/7 -X PATCH -f state=closed

echo [8] Apagando Issue 8...
gh api repos/%REPO%/issues/8 -X PATCH -f state=closed

echo [9] Apagando Issue 9...
gh api repos/%REPO%/issues/9 -X PATCH -f state=closed

echo [10] Apagando Issue 10...
gh api repos/%REPO%/issues/10 -X PATCH -f state=closed

echo.
echo ============================================
echo Issues antigas fechadas!
echo Agora rode: criar_issues_radar_v2.bat
echo ============================================
pause