@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0"
cl /nologo /EHsc /std:c++17 /O2 /fp:strict /W4 /LD temporal_extension.cpp /Fe:independent.dll /Fo:independent.obj
exit /b %errorlevel%
