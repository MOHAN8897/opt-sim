@echo off
echo =========================================
echo Starting ngrok tunnel for FRONTEND (5173)
echo =========================================
echo.
echo Keep this window open!
echo The ngrok URL will appear below.
echo.

ngrok http 5173
