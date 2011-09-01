from celery.task import task
import os
import sys
import collada
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
from content.utils import get_file_metadata, get_hash, save_file_data, add_metadata
import os.path
import posixpath
import Image
import hashlib
import multiprocessing

def get_screenshot(dae_data, subfile_map):
    from meshtool.filters.panda_filters import pandacore
    from meshtool.filters.panda_filters import save_screenshot
    
    def customImageLoader(filename):
        return subfile_map[posixpath.basename(filename)]
    
    mesh = collada.Collada(StringIO(dae_data), aux_file_loader=customImageLoader)

    p3dApp = pandacore.setupPandaApp(mesh)
    im = pandacore.getScreenshot(p3dApp)
    im.load()
    if 'A' in list(im.getbands()):
        bbox = im.split()[list(im.getbands()).index('A')].getbbox()
        im = im.crop(bbox)
    main_screenshot = StringIO()
    im.save(main_screenshot, "PNG", optimize=1)
    main_screenshot = main_screenshot.getvalue()
    
    return main_screenshot

def _get_screenshot(queue, dae_data, subfile_map):
    try:
        ss = get_screenshot(dae_data, subfile_map)
        queue.put(ss)
    except:
        queue.put(None)

@task
def generate_screenshot(filename, typeid):
    metadata = get_file_metadata(filename)
    hash = metadata['types'][typeid]['hash']
    subfiles = metadata['types'][typeid]['subfiles']
    
    dae_data = get_hash(hash)['data']

    subfile_map = {}
    for subfile in subfiles:
        img_meta = get_file_metadata(subfile)
        img_hash = img_meta['hash']
        img_data = get_hash(img_hash)['data']
        base_name = os.path.basename(os.path.split(subfile)[0])
        subfile_map[base_name] = img_data
    
    #The below is a total hack and I feel really dirty doing it, but
    # there is no way to get panda3d to clean up after itself except to
    # exit the process. Celery workers are run as a daemon, so they can't
    # create child processes. Doing so could cause orphaned, defunct processes.
    # I'm doing it anyway because I haven't found any other way to do this. Sorry.
    q = multiprocessing.Queue()
    daemonic = multiprocessing.current_process()._daemonic
    multiprocessing.current_process()._daemonic = False
    p = multiprocessing.Process(target=_get_screenshot, args=[q, dae_data, subfile_map])
    p.start()
    main_screenshot = q.get()
    p.join()
    multiprocessing.current_process()._daemonic = daemonic
    
    im = Image.open(StringIO(main_screenshot))
    thumbnail = StringIO()
    im.thumbnail((96,96), Image.ANTIALIAS)
    im.save(thumbnail, "PNG", optimize=1)
    thumbnail = thumbnail.getvalue()
    
    main_key = hashlib.sha256(main_screenshot).hexdigest()
    thumb_key = hashlib.sha256(thumbnail).hexdigest()
    save_file_data(main_key, main_screenshot, "image/png")
    save_file_data(thumb_key, thumbnail, "image/png")
    
    ss_info = {'screenshot': main_key, 'thumbnail': thumb_key}
    base_filename, version_num = os.path.split(filename)
    add_metadata(base_filename, version_num, typeid, ss_info)

