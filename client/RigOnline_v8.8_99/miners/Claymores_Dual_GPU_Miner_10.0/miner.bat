@echo off

setx GPU_FORCE_64BIT_PTR 0
setx GPU_MAX_HEAP_SIZE 100
setx GPU_USE_SYNC_OBJECTS 1
setx GPU_MAX_ALLOC_PERCENT 100
setx GPU_SINGLE_ALLOC_PERCENT 100

:: Применение профиля MSI Afterburner
"C:\Program Files (x86)\MSI Afterburner\MSIAfterburner.exe" -Profile1

:: Запуск майнера
EthDcrMiner64.exe -epool eu1.ethermine.org:4444 -ewal 0x38ae6fb78a90bf36e1c63e0db9d0a17dad03da2f.noname -epsw x -dbg -1