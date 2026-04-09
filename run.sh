#!/bin/bash
cd "$(dirname "$0")"
streamlit run app.py --server.headless true --browser.gatherUsageStats false
