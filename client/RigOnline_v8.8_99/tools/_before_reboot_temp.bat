@echo off

:: закрываем майнер
taskkill /f /im EthDcrMiner64.exe
taskkill /f /im miner.exe
taskkill /f /im Optiminer.exe
taskkill /f /im NsGpuCNMiner.exe
taskkill /f /im prospector.exe
taskkill /f /im ccminer.exe
taskkill /f /im ethminer.exe
taskkill /f /im excavator.exe
taskkill /f /im nheqminer.exe
taskkill /f /im sgminer.exe

:: запукаем майнер
start "" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\bitfinex_(etc-ethermine).bat.lnk"
