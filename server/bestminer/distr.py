import logging
from zipfile import ZipFile
import os

logger = logging.getLogger(__name__)

def miners_zip():
    '''
    make zip for all miners located in client/miners
    :return:
    '''
    # directory of this script location
    script_path = os.path.dirname(__file__)
    # where to put distributive on the server
    target_dir = os.path.join(script_path, 'static/miners/')
    # client source dir
    source_dir = os.path.join(script_path, '../../client/miners')

    logger.info("Prepare zip files for miners")
    for miner_dir in os.listdir(source_dir):
        zip_name = miner_dir + ".zip"
        logger.info("miner %s " % miner_dir)
        with ZipFile(os.path.join(target_dir, zip_name), 'w') as myzip:
            for root, dirs, files in os.walk(os.path.join(source_dir, miner_dir)):
                for file in files:
                    if file == '.gitignore':
                        continue
                    fn = os.path.join(root, file)
                    rel = os.path.relpath(os.path.join(root, file), source_dir)
                    myzip.write(fn, arcname=rel)
        logger.info("... done")


def client_zip_windows_for_update():
    '''
    create client ZIP file for client autoupdate.
    Shall be run once new client version release
    :return: str of ZIP location on the server.
    '''
    script_path = os.path.dirname(__file__)
    zip_location = os.path.join(script_path, 'static/client/BestMiner-Windows.zip')
    _client_zip_windows(
        client_config={'email': '', 'secret': ''},
        zip_location=zip_location,
        client_dir="."
    )
    return zip_location

def client_zip_windows_for_user(user, server):
    '''
    create client ZIP for download and install by user.
    Fill user settings in config.txt
    :return: str of ZIP location on the server. For download flask.redirect(request.host_url + zip_location)
    '''
    config = {'email': user.email, 'secret': user.client_secret, 'server': server}
    script_path = os.path.dirname(__file__)
    zip_dir_on_server = 'static/client/gen/{}/'.format(user.id)
    zip_filename = 'BestMiner-Windows.zip'
    zip_file_on_server = os.path.join(zip_dir_on_server, zip_filename)
    zip_dir_on_disk = os.path.join(script_path, zip_dir_on_server)
    os.makedirs(zip_dir_on_disk, exist_ok=True)
    zip_file_on_disk = os.path.join(zip_dir_on_disk, zip_filename)
    _client_zip_windows(config, zip_file_on_disk, 'BestMiner')
    return zip_file_on_server


def _client_zip_windows(client_config={}, zip_location='static/client/BestMiner-Windows.zip', client_dir="."):
    '''

    :param client_dir:  root directory in client archive
    :param client_config: will be saved as content of config.txt
    :param zip_location: where to put distributive on the server (directory path shall exist!)
    :return:
    '''
    # client source dir
    script_path = os.path.dirname(__file__)
    source_dir = os.path.join(script_path, '../../client')
    # prefix of directories/files to add to archive
    includes = '''
bestminer-client.py
epython
ChangeLog.txt
BestMiner.bat
version.txt
'''
    include = set(includes.split())
    logger.info("Building bestminer client in %s" % zip_location)
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
        # Now let's save config file for client
        if client_config:
            strings = []
            for k,v in client_config.items():
                strings.append("{}={}".format(k,v))
            config_txt = "\r\n".join(strings)

            rel = os.path.join(client_dir, "config.txt")
            myzip.writestr(rel, config_txt)
        logger.info("... done")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("RUN generation of ZIP files for client")
    client_zip_windows_for_update()
    miners_zip()