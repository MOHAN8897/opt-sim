@echo off
echo =========================================
echo Starting ngrok tunnel for BACKEND (8000)
echo =========================================
echo.
echo Keep this window open!
echo The ngrok URL will appear below.
echo.

ngrok http 8000
