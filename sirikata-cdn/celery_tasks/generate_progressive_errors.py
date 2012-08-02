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

def get_progressive_errors(dae_data, pm_data, mipmap_tar_data):
    from meshtool.filters.print_filters.print_pm_perceptual_error import getPmPerceptualError
    
    mesh = collada.Collada(StringIO(dae_data))
    pm_filebuf = StringIO(pm_data) if pm_data is not None else None
    mipmap_tarfilebuf = StringIO(mipmap_tar_data)
    
    error_data = getPmPerceptualError(mesh, pm_filebuf, mipmap_tarfilebuf)
    
    return error_data

def _get_progressive_errors(queue, dae_data, pm_data, mipmap_tar_data):
    try:
        error_data = get_progressive_errors(dae_data, pm_data, mipmap_tar_data)
        queue.put(error_data)
    except:
        queue.put(None)

@task
def generate_progressive_errors(filename, typeid):
    if typeid != 'progressive':
        return
    
    metadata = get_file_metadata(filename)
    hash = metadata['types'][typeid]['hash']
    subfiles = metadata['types'][typeid]['subfiles']
    progressive_stream_hash = metadata['types'][typeid]['progressive_stream']
    mipmap_tar_hash = metadata['types'][typeid]['mipmaps'].values()[0]['hash']
    
    dae_data = get_hash(hash)['data']
    pm_data = get_hash(progressive_stream_hash)['data'] if progressive_stream_hash is not None else None
    mipmap_tar_data = get_hash(mipmap_tar_hash)['data']
    
    #The below is a total hack and I feel really dirty doing it, but
    # there is no way to get panda3d to clean up after itself except to
    # exit the process. Celery workers are run as a daemon, so they can't
    # create child processes. Doing so could cause orphaned, defunct processes.
    # I'm doing it anyway because I haven't found any other way to do this. Sorry.
    q = multiprocessing.Queue()
    daemonic = multiprocessing.current_process()._daemonic
    multiprocessing.current_process()._daemonic = False
    p = multiprocessing.Process(target=_get_progressive_errors, args=[q, dae_data, pm_data, mipmap_tar_data])
    p.start()
    error_data = q.get()
    p.join()
    multiprocessing.current_process()._daemonic = daemonic
    
    if error_data is None:
        return
    
    error_info = {'progressive_perceptual_error': error_data}
    base_filename, version_num = os.path.split(filename)
    add_metadata(base_filename, version_num, typeid, error_info)

