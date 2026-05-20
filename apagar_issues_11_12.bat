@echo off
REM Apagar Issues 11 e 12 (criadas com body vazio)
set REPO=GilvanS/historico-clash-roayle

echo.
echo === Apagando Issues 11 e 12 ===
echo.

echo [1] Fechando Issue 11...
gh api repos/%REPO%/issues/11 -X PATCH -f state=closed

echo [2] Fechando Issue 12...
gh api repos/%REPO%/issues/12 -X PATCH -f state=closed

echo.
echo === Issues 11 e 12 fechadas! ===
echo.
pause