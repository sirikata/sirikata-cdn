import collada as coll
from celery.task import task
from celery.execute import send_task
import cassandra_storage.cassandra_util as cass
from content.utils import save_file_data
from StringIO import StringIO
import Image
import zipfile
import os.path
import hashlib
import json

import time
import sys

class DatabaseError(Exception):
    """Raised if an exception is raised during cassandra operations"""
    pass
class NoDaeFound(Exception):
    """Raised when an archive doesn't contain a .dae file"""
    pass
class TooManyDaeFound(Exception):
    """Raised when an archive contains more than one .dae file
     self.names contains the list of .dae files in the archive"""
    def __init__(self, names, *args, **kwargs):
        super(TooManyDaeFound,self).__init__(names, *args, **kwargs)
        self.names = names
class SubFilesNotFound(Exception):
    """Raised when a .dae file depends on other files (e.g. textures)
    and those files cannot be found"""
    def __init__(self, names, *args, **kwargs):
        super(SubFilesNotFound,self).__init__(names, *args, **kwargs)
        self.names = names
class ColladaError(Exception):
    """Base class for any collada exception"""
    def __init__(self, orig, *args, **kwargs):
        super(ColladaError,self).__init__(orig, *args, **kwargs)
        self.orig = orig
class ImageError(Exception):
    """Raised when a given image doesn't load properly"""
    def __init__(self, filename, *args, **kwargs):
        super(ImageError,self).__init__(filename, *args, **kwargs)
        self.filename = filename

def save_file_name(path, version_num, hash_key, length):
    cf = cass.getColumnFamily("Names")
    
    dict = {'hash': hash_key, 'size': length}
    col_val = json.dumps(dict)
    
    cf = cass.getColumnFamily("Names")
    try:
        cass.insertRecord(cf, path, columns={version_num: col_val})
    except cass.DatabaseError:
        raise DatabaseError()

def save_version_type(path, version_num, hash_key, length, subfile_names, title, description, type_id):
    cf = cass.getColumnFamily("Names")
    
    try:
        rec = cass.getRecord(cf, path, columns=[version_num])
        version_dict = json.loads(rec[version_num])
    except cass.NotFoundError:
        version_dict = {}
    except cass.DatabaseError:
        raise DatabaseError()
    
    if 'types' not in version_dict:
        version_dict['types'] = {}
    
    if 'title' not in version_dict:
        version_dict['title'] = title
    if 'description' not in version_dict:
        version_dict['description'] = description
    
    version_dict['types'][type_id] = {'hash': hash_key,
                                      'size': length,
                                      'subfiles': subfile_names}
    
    try:
        cass.insertRecord(cf, path, columns={version_num: json.dumps(version_dict)})
    except cass.DatabaseError:
        raise DatabaseError()

def get_new_version_from_path(path, file_type):
    cf = cass.getColumnFamily("Names")
    
    try:
        rec = cass.getRecord(cf, path, columns=["latest"])
        latest = str(int(rec['latest'])+1)
    except cass.NotFoundError:
        latest = "0"
    except cass.DatabaseError:
        raise DatabaseError()

    try:
        cass.insertRecord(cf, path, columns={"latest":latest, "type":file_type})
    except cass.DatabaseError:
        raise DatabaseError()

    return latest

def get_temp_file(rowkey):
    cf = cass.getColumnFamily("TempFiles")

    try:
        rec = cass.getRecord(cf, rowkey, columns=["size", "chunk_list"])
    except cass.DatabaseError:
        raise DatabaseError()
    file_size = rec['size']
    chunk_list = rec['chunk_list'].split(',')
    
    try:
        chunks = cass.getRecord(cf, rowkey, columns=chunk_list)
    except cass.DatabaseError:
        raise DatabaseError()
    file_data = ''.join([chunks[c] for c in chunk_list])
    return file_data

def get_file_or_zip(file_data, selected_dae):
    try:
        zip = zipfile.ZipFile(StringIO(file_data), 'r')
        
        dae_names = []
        for name in zip.namelist():
            if name.upper().endswith('.DAE'):
                dae_names.append(name)
        
        if len(dae_names) == 0:
            raise NoDaeFound()
        elif len(dae_names) > 1 and \
            (selected_dae is None or selected_dae not in dae_names):
            raise TooManyDaeFound(dae_names)
        
        if selected_dae:
            dae_zip_name = selected_dae
        else:
            dae_zip_name = dae_names[0]
        
        dae_data = zip.read(dae_zip_name)
    except zipfile.BadZipfile:
        zip = None
        dae_zip_name = None
        dae_data = file_data
        
    return (zip, dae_zip_name, dae_data)

def get_collada_and_images(zip, dae_zip_name, dae_data, subfiles):
    try:
        col = coll.Collada(StringIO(dae_data))
    except coll.DaeError as err:
        raise ColladaError(str(err))

    not_found_list = []
    subfile_data = {}

    #TODO: Use of os.path would likely break on windows
    for img in col.images:
        rel_path = img.path
        base_name = os.path.basename(img.path)
        
        if base_name in subfiles:
            img_data = get_temp_file(subfiles[base_name])
            subfile_data[base_name] = img_data
        elif dae_zip_name is not None:
            dae_prefix = os.path.split(dae_zip_name)[0]
            concat_path = os.path.join(dae_prefix, rel_path)
            norm_path = os.path.normpath(concat_path)
            if norm_path in zip.namelist():
                img_data = zip.read(norm_path)
                subfile_data[base_name] = img_data
            else:
                not_found_list.append(base_name)
        else:
            not_found_list.append(base_name)

    if len(not_found_list) > 0:
        raise SubFilesNotFound(not_found_list)
    
    image_objs = {}
    for image_name, image_data in subfile_data.iteritems():
        try:
            im = Image.open(StringIO(image_data))
            im.load()
        except IOError:
            raise ImageError(image_name)
        image_objs[image_name] = im
        
    return (col, subfile_data, image_objs)

@task
def import_upload(main_rowkey, subfiles, selected_dae=None):
    """main_rowkey should be a row key that points to the row in TempFiles
    that contains the main (.dae) file.
    selected_dae is an optional parameter that selects the dae file in an
    archive that containes multiple dae files
    subfiles is a dict where the key is the file name string and the value is
    the row key in TempFiles that contains the file
    e.g. ('fe389', {'sub.jpg':'39c4d'}) """
    
    import_upload.update_state(state="LOADING")
    file_data = get_temp_file(main_rowkey)
    (zip, dae_zip_name, dae_data) = get_file_or_zip(file_data, selected_dae)
    
    import_upload.update_state(state="CHECKING_COLLADA")
    get_collada_and_images(zip, dae_zip_name, dae_data, subfiles)

@task
def place_upload(main_rowkey, subfiles, title, path, description, selected_dae=None):
    import_upload.update_state(state="LOADING")
    file_data = get_temp_file(main_rowkey)
    (zip, dae_zip_name, dae_data) = get_file_or_zip(file_data, selected_dae)
    
    import_upload.update_state(state="CHECKING_COLLADA")
    (collada_obj, subfile_data, image_objs) = get_collada_and_images(zip, dae_zip_name, dae_data, subfiles)

    import_upload.update_state(state="SAVING_ORIGINAL")
    new_version_num = get_new_version_from_path(path, file_type="collada")
    
    #Make sure image paths are just the base name
    current_prefix = "original"
    subfile_names = []
    for img in collada_obj.images:
        rel_path = img.path
        base_name = os.path.basename(img.path)
        img.path = "./%s" % base_name
        img.save()
        img_hex_key = hashlib.sha256(subfile_data[base_name]).hexdigest()
        try: save_file_data(img_hex_key, subfile_data[base_name], "image/%s" % image_objs[base_name].format.lower())
        except: raise DatabaseError()
        img_path = "%s/%s/%s" % (path, current_prefix, base_name)
        img_len = len(subfile_data[base_name])
        img_version_num = get_new_version_from_path(img_path, file_type="image")
        save_file_name(img_path, img_version_num, img_hex_key, img_len)
        subfile_names.append("%s/%s" % (img_path, img_version_num))

    str_buffer = StringIO()
    collada_obj.root.write(str_buffer)
    orig_save_data = str_buffer.getvalue()
    orig_hex_key = hashlib.sha256(orig_save_data).hexdigest()
    try: save_file_data(orig_hex_key, orig_save_data, "application/xml")
    except: raise DatabaseError()
    save_version_type(path, new_version_num, orig_hex_key, len(orig_save_data),
                      subfile_names, title, description, "original")

    path_with_vers = "%s/%s" % (path, new_version_num)

    send_task("celery_tasks.generate_screenshot.generate_screenshot", args=[path_with_vers, "original"])
    
    return path_with_vers