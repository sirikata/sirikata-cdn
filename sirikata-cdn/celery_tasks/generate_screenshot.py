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

def _generate_screenshot(filename, typeid):

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
    
    def customImageLoader(filename):
        return subfile_map[posixpath.basename(filename)]
    
    mesh = collada.Collada(StringIO(dae_data), aux_file_loader=customImageLoader)

    from meshtool.filters.panda_filters import pandacore
    from meshtool.filters.panda_filters import save_screenshot
    p3dApp = pandacore.setupPandaApp(mesh)
    im = pandacore.getScreenshot(p3dApp)
    im.load()
    if 'A' in list(im.getbands()):
        bbox = im.split()[list(im.getbands()).index('A')].getbbox()
        im = im.crop(bbox)
    main_screenshot = StringIO()
    im.save(main_screenshot, "PNG", optimize=1)
    main_screenshot = main_screenshot.getvalue()
    
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
    
    p3dApp.destroy()

@task
def generate_screenshot(filename, typeid):
    forkid = os.fork()
    if forkid == 0:
        _generate_screenshot(filename, typeid)
        sys.exit(0)
    else:
        (childid, status) = os.waitpid(forkid, 0)
        if status != 0:
            raise Exception("Screenshot generation failed")
