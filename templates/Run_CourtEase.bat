
@echo off
cd /d "C:\Users\Chaitanya\DBMS project"
echo Starting CourtEase...
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
