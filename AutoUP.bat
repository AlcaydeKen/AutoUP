@echo off
setlocal enabledelayedexpansion

set "FOLDER_TO_UPLOAD=C:\AutoUP\PDF"
set "CREDENTIALS_FILE=C:\AutoUP\Credentials\credentials.json"
set "PROTECTED_PDF_FOLDER_PATH=C:\AutoUP\Protected_PDF"

python AutoUp.py "%FOLDER_TO_UPLOAD%" "%CREDENTIALS_FILE%" "%PROTECTED_PDF_FOLDER_PATH%"

pause > nul

