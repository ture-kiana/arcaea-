@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 检查资源文件...
python scripts\fetch_assets.py || goto :err

echo.
echo [2/3] 检查 adb...
if not exist "app\tools\adb.exe" (
  echo   缺少 app\tools\adb.exe，请把 Android platform-tools 里的
  echo   adb.exe / AdbWinApi.dll / AdbWinUsbApi.dll 放进 app\tools\ 后重试。
  goto :err
)

echo.
echo [3/3] 打包...
python -m PyInstaller --noconfirm --onefile --noconsole --name "ArcaeaB50" ^
  --icon "app\icon.ico" ^
  --add-data "%CD%\app\ui.html;." ^
  --add-data "%CD%\app\data;data" ^
  --add-data "%CD%\app\viewer;viewer" ^
  --add-data "%CD%\app\tools;tools" ^
  --distpath "%CD%\dist" --workpath "%CD%\build_app" --specpath "%CD%\build_app" ^
  "%CD%\app\main.py"
if errorlevel 1 goto :err

echo.
echo 完成：dist\ArcaeaB50.exe
pause
exit /b 0

:err
echo.
echo 构建失败，请查看上面的错误信息。
pause
exit /b 1
