@echo off

:: ���������� ���� ��������������
tools\devcon_x64.exe restart =display

:: �����
timeout /T 10

:: ���������� ������� MSI Afterburner
"C:\Program Files (x86)\MSI Afterburner\MSIAfterburner.exe" -Profile1
