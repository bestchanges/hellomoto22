from cx_Freeze import setup, Executable

setup(
    name = "best_miner",
    version = "0.1",
    description = "Best Miner Client App",
    executables = [Executable("bestminer-client.py")]
)