from zipfile import ZipFile
import os


def client_zip():
    # root directory in client archive
    client_dir = "BestMiner"
    # where to put distributive on the server
    zip_location = 'static/client/BestMiner-win64.zip'
    # client source dir
    dirname = '../client'
    # prefix of directories/files to add to archive
    includes = '''
ccminer-cryptonight-200-x64
claymore10
config.ini
ewbf_0.3.4b
bestminer-client.py
miner_emu
OpenHardwareMonitor
python_win
run.bat
version.txt
'''
    include = set(includes.split())
    with ZipFile(zip_location, 'w') as myzip:
        for root, dirs, files in os.walk(dirname):
            for file in files:
                fn = os.path.join(root, file)
                rel = os.path.relpath(os.path.join(root, file), dirname)
                do_add = False
                for prefix in include:
                    if rel.startswith(prefix):
                        do_add = True
                        break
                if do_add:
                    rel = os.path.join(client_dir, rel)
                    myzip.write(fn, arcname=rel)

client_zip()