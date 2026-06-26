@echo off
:: Launch Microsoft Edge with remote debugging port for CDP connection.
:: Required by yt-deepseek-summarizer.

set EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if not exist "%EDGE%" set EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe

if not exist "%EDGE%" (
    echo Edge not found. Please install Microsoft Edge.
    pause
    exit /b 1
)

echo Killing existing Edge processes ...
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Launching Edge with debug port 9222 ...
start "" "%EDGE%" --remote-debugging-port=9222

timeout /t 3 /nobreak >nul
echo.
echo Edge launched. You can now run: python yt_to_deepseek.py "YOUTUBE_URL"
pause
