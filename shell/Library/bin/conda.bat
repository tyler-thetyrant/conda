@REM @SET _CONDA_EXE="%~dp0..\..\Scripts\conda.exe"

@IF NOT "%_CONDA_EXE%" == "" GOTO skip_conda_exe_dev
    @IF "%CONDA_PYTHON_EXE%" == "" (
        @SET "_CONDA_EXE=python "%~dp0..\..\bin\conda""
    ) ELSE (
        @SET "_CONDA_EXE="%CONDA_PYTHON_EXE%" "%~dp0..\..\bin\conda""
    )
:skip_conda_exe_dev

@FOR /F "delims=" %%i IN ('@python -c "import ctypes; print(ctypes.cdll.kernel32.GetACP())"') DO @SET "PYTHONIOENCODING=%%i"
@chcp %PYTHONIOENCODING% > NUL

@IF "%1"=="activate" GOTO :DO_ACTIVATE
@IF "%1"=="deactivate" GOTO :DO_DEACTIVATE

@CALL %_CONDA_EXE% %*

@REM This block should really be the equivalent of
@REM   if "install" in %* GOTO :DO_REACTIVATE
@IF "%1"=="install" GOTO :DO_REACTIVATE
@IF "%1"=="update" GOTO :DO_REACTIVATE
@IF "%1"=="remove" GOTO :DO_REACTIVATE
@IF "%1"=="uninstall" GOTO :DO_REACTIVATE

@GOTO :End


:DO_ACTIVATE
@FOR /F "delims=" %%i IN ('@CALL %_CONDA_EXE% shell.cmd.exe activate %*') DO @SET "_TEMP_SCRIPT_PATH=%%i"
@IF "%_TEMP_SCRIPT_PATH%"=="" GOTO :ErrorEnd
@IF "%CONDA_PROMPT_MODIFIER%" == "" GOTO skip_prompt_set_activate
    @CALL SET "PROMPT=%%PROMPT:%CONDA_PROMPT_MODIFIER%=%_empty_not_set_%%%"
:skip_prompt_set_activate
@CALL "%_TEMP_SCRIPT_PATH%"
@DEL /F /Q "%_TEMP_SCRIPT_PATH%"
@SET _TEMP_SCRIPT_PATH=
@SET "PROMPT=%CONDA_PROMPT_MODIFIER%%PROMPT%"
@GOTO :End

:DO_DEACTIVATE
@FOR /F "delims=" %%i IN ('@CALL %_CONDA_EXE% shell.cmd.exe deactivate %*') DO @SET "_TEMP_SCRIPT_PATH=%%i"
@IF "%_TEMP_SCRIPT_PATH%"=="" GOTO :ErrorEnd
@IF "%CONDA_PROMPT_MODIFIER%" == "" GOTO skip_prompt_set_deactivate
    @CALL SET "PROMPT=%%PROMPT:%CONDA_PROMPT_MODIFIER%=%_empty_not_set_%%%"
:skip_prompt_set_deactivate
@CALL "%_TEMP_SCRIPT_PATH%"
@DEL /F /Q "%_TEMP_SCRIPT_PATH%"
@SET _TEMP_SCRIPT_PATH=
@SET "PROMPT=%CONDA_PROMPT_MODIFIER%%PROMPT%"
@GOTO :End

:DO_REACTIVATE
@FOR /F "delims=" %%i IN ('@CALL %_CONDA_EXE% shell.cmd.exe reactivate %*') DO @SET "_TEMP_SCRIPT_PATH=%%i"
@IF "%_TEMP_SCRIPT_PATH%"=="" GOTO :ErrorEnd
@CALL "%_TEMP_SCRIPT_PATH%"
@DEL /F /Q "%_TEMP_SCRIPT_PATH%"
@SET _TEMP_SCRIPT_PATH=
@GOTO :End

:End
@SET _CONDA_EXE=
@GOTO :EOF

:ErrorEnd
@SET _CONDA_EXE=
@EXIT /B 1
