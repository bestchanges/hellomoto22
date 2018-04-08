./watchdog.sh &
cd bestminer
screen -dm -S miner bash -c "./bestminer.sh" &
