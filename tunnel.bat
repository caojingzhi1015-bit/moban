@echo off
cd /d "d:\KuGou\Lyric\简介生成 - 副本"
echo Starting Cloudflare Tunnel for CareerAI...
echo.
cloudflared.exe tunnel --url http://localhost:8501
pause
