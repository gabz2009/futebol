@echo off
rem Corre o pipeline completo (downloads, ETL, previsões e warehouse) e guarda tudo em dados\agendamento.log.
rem É este ficheiro que o Agendador de Tarefas do Windows corre todos os dias.
cd /d %~dp0
set PYTHONUTF8=1
echo ===== %date% %time% ===== >> dados\agendamento.log
.venv\Scripts\python.exe etl\executar_tudo.py >> dados\agendamento.log 2>&1
echo Terminou com o codigo %errorlevel% >> dados\agendamento.log
exit /b %errorlevel%