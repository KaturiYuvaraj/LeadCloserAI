@echo off
echo ============================================================
echo   Starting Telugu AI Caller & Sales Closing CRM Server
echo   Speech-to-Text: Sarvam Saaras (Telugu / Tenglish)
echo   Text-to-Speech: Sarvam Bulbul Flash (Kavitha Voice)
echo   Sales LLM Engine: Sarvam 105B Conversational
echo ============================================================
echo.
cd /d "%~dp0\telugu-ai-caller"
call venv\Scripts\activate.bat
python main.py
pause

