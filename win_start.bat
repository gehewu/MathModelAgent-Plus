@echo off
chcp 65001 >nul
echo ==============================================
echo  一键启动 Redis + 后端FastAPI + 前端Vue/React
echo ==============================================
echo.

:: ====================== 启动 Redis（已在运行则跳过） ======================
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo Redis 未运行，正在启动...
    start "Redis 服务" cmd /k "redis-server"
) else (
    echo Redis 已在运行，跳过启动
)

:: ====================== 启动 后端 ======================
start "后端服务" cmd /k "cd /d .\backend && .\.venv\Scripts\Activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8001 --ws-ping-interval 60 --ws-ping-timeout 120 --reload"

:: ====================== 启动 前端 ======================
start "前端服务" cmd /k "cd /d .\frontend && pnpm run dev"

echo 三个服务已全部启动！
echo.
pause