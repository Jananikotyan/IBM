@echo off
echo ============================================
echo  Sehat Saathi - ngrok Tunnel Launcher
echo ============================================
echo.
echo Starting ngrok tunnel on port 8000...
echo.
echo When ngrok starts, look for a line like:
echo   Forwarding  https://abc123.ngrok-free.app -^> http://localhost:8000
echo.
echo Copy that https URL and paste it into:
echo   Twilio Console ^> WhatsApp Sandbox Settings
echo   Set webhook to: https://abc123.ngrok-free.app/whatsapp/incoming
echo.
echo Press Ctrl+C to stop the tunnel.
echo ============================================
echo.
"C:\Users\janani\IBM\sehat-saathi\ngrok.exe" http 8000
