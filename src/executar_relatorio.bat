@echo off
REM ============================================
REM Script para executar relatorio de oponentes
REM ============================================

REM CONFIGURE AQUI SEU TOKEN E TAG
set CR_API_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjkwODQxMGZlLTdiNjgtNGI1Ny04YWU5LWVhMTE2YWZiODMxYyIsImlhdCI6MTc2NTQ5Mzk4OSwic3ViIjoiZGV2ZWxvcGVyLzllZjZlMmQ2LTQ1ZmEtYjdkMi1jZGI2LTZmYWJmODA0NWFiZiIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyI0NS43OS4yMTguNzkiXSwidHlwZSI6ImNsaWVudCJ9XX0.pDhAHyZ2tAR5dg2QwBXabKTryUvaT7N9QxFKDUSrvZ_1P99x3hLP1oXy49Y9E4a4Ty_TiiUgqd5BTYzwO1Z3wA
set CR_PLAYER_TAG=#2QR292P

REM Executa o script
echo Executando relatorio de oponentes...
echo.
python opponents_report.py

echo.
echo Relatorio gerado com sucesso!
pause

