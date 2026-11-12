@echo off
rem Stable entry point for Git on this machine (Git is not on PATH).
rem Usage: coordination\git.cmd status
setlocal
set "GIT_BIN=D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe"
if defined GIT_EXE set "GIT_BIN=%GIT_EXE%"
"%GIT_BIN%" %*
endlocal
