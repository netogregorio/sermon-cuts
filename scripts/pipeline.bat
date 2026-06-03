@echo off
REM Windows wrapper around pipeline.py.
REM
REM All orchestration lives in pipeline.py — this just hands off so
REM Windows users can run "pipeline.bat <source>" the same way macOS
REM and Linux users run "pipeline.sh <source>".
REM
REM Run "python pipeline.py --help" for the full flag surface.

python "%~dp0pipeline.py" %*
