@echo off
setlocal
cd /d "%~dp0"
echo Starting DeepLister local demo...
echo Open http://localhost:8505 after Streamlit starts.
python -m streamlit run streamlit_app.py --server.port 8505 --server.headless false
pause
