@echo off
REM If no argument, list hotpaths:
if "%~1"=="" (
    ceol.exe
    goto :eof
)

REM With argument: extract path and cd if found
for /f "delims=" %%P in ('ceol.exe %1') do (
    if not "%%P"=="" cd /d "%%P"
)
