@echo off
title News Crawler
cd /d "%~dp0"
streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause
