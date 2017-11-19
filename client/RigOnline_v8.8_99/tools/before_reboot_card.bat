@echo off

:: Перезапуск всех видеоадаптеров
tools\devcon_x64.exe restart =display

:: Пауза
timeout /T 10

:: Применение профиля MSI Afterburner
"C:\Program Files (x86)\MSI Afterburner\MSIAfterburner.exe" -Profile1
