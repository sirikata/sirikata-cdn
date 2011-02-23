import collada as coll
from celery.task import task
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
import zipfile
import os.path

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

def get_temp_file(rowkey):
    cf = cass.getColumnFamily("TempFiles")

    try:
        rec = cass.getRecord(cf, rowkey, columns=["size", "chunk_list"])
    except cass.DatabaseError:
        raise DatabaseError()
    file_size = rec['size']
    chunk_list = rec['chunk_list'].split(',')
    
    #import_upload.update_state(state="READING")
    
    try:
        chunks = cass.getRecord(cf, rowkey, columns=chunk_list)
    except cass.DatabaseError:
        raise DatabaseError()
    file_data = ''.join([chunks[c] for c in chunk_list])
    return file_data

@task
def import_upload(main_rowkey, subfiles, selected_dae=None):
    """main_rowkey should be a row key that points to the row in TempFiles
    that contains the main (.dae) file.
    selected_dae is an optional parameter that selects the dae file in an
    archive that containes multiple dae files
    subfiles is a dict where the key is the file name string and the value is
    the row key in TempFiles that contains the file
    e.g. ('fe389', {'sub.jpg':'39c4d'}) """
    
    file_data = get_temp_file(main_rowkey)
    
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
        dae_zip_name = None
        dae_data = file_data
    
    #import_upload.update_state(state="LOADING")
    
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
    
    return "nice"
    
if __name__ == "__main__":
    #print import_upload(sys.argv[1], [])
    #print import_upload('a80897caa39a40e3a50c5b4b1c835961', []) #ducknested.zip
    #print import_upload('65ee819384fb4e1cb95a5665486b06c6', []) #duck.zip
    #print import_upload('da834bbf55af4217859ea701d40aac14', []) #ducknone.zip
    #print import_upload('c8c13de03b504b5db89fa167186776cc', []) #duck.2.zip
    print import_upload('c90b170b22c84c3a91fa7dbf13929f00', []) #duck.missing.sub.zip
    
