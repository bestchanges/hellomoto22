from zipfile import ZipFile
import os


def miners_zip():
    '''
    make zip for all miners located in client/miners
    :return:
    '''
    # where to put distributive on the server
    target_dir = 'static/miners/'
    # client source dir
    source_dir = '../client/miners'

    print("Prepare zip files for miners")
    for miner_dir in os.listdir(source_dir):
        zip_name = miner_dir + ".zip"
        print("miner %s " % miner_dir)
        with ZipFile(os.path.join(target_dir, zip_name), 'w') as myzip:
            for root, dirs, files in os.walk(os.path.join(source_dir, miner_dir)):
                for file in files:
                    if file == '.gitignore':
                        continue
                    fn = os.path.join(root, file)
                    rel = os.path.relpath(os.path.join(root, file), source_dir)
                    myzip.write(fn, arcname=rel)
    print("... done")


def client_zip_windows():
    # root directory in client archive
    client_dir = "."
    # where to put distributive on the server
    zip_location = 'static/client/BestMiner-Windows.zip'
    # client source dir
    source_dir = '../client'
    # prefix of directories/files to add to archive
    includes = '''
config.txt
bestminer-client.py
distr_win
epython
BestMiner.bat
version.txt
'''
    include = set(includes.split())
    print("Building bestminer client in %s" % zip_location)
    with ZipFile(zip_location, 'w') as myzip:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                fn = os.path.join(root, file)
                rel = os.path.relpath(os.path.join(root, file), source_dir)
                do_add = False
                for prefix in include:
                    if rel.startswith(prefix):
                        do_add = True
                        break
                if do_add:
                    rel = os.path.join(client_dir, rel)
                    myzip.write(fn, arcname=rel)
    print("... done")

if __name__ == '__main__':
    client_zip_windows()
    miners_zip()