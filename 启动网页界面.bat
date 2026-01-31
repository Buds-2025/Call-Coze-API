@echo off
chcp 65001 >nul
title Coze API 网页终端启动器
echo 正在启动 Coze API 网页界面...
echo.
python -m streamlit run app.py
pause
