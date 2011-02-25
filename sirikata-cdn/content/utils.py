from cassandra_storage.cassandra_util import *
import json

NAMES = getColumnFamily('Names')
FILES = getColumnFamily('Files')

def get_file_metadata(filename):
    split = filename.split("/")
    
    version = split[-1:][0]
    file_key = "/".join(split[:-1])
    
    try:
        rec = getRecord(NAMES, file_key, columns=[version, "type"])
    except DatabaseError:
        raise
    
    version_data = json.loads(rec[version])
    version_data['type'] = rec['type']
    return version_data

def get_hash(hash):
    try:
        rec = getRecord(FILES, hash, columns=['data', 'mimetype'])
    except:
        raise
    
    return rec

def save_file_data(hash, data, mimetype):
    try:
        rec = getRecord(FILES, hash, columns=[])
        #already exists so return
        return
    except NotFoundError:
        pass
    except DatabaseError:
        raise
    
    try:
        rec = insertRecord(FILES, hash, columns={"data": data, "mimetype": mimetype})
    except DatabaseError:
        raise DatabaseError()

def add_metadata(path, version_num, type_id, metadata):    
    rec = getRecord(NAMES, path, columns=[version_num])
    version_dict = json.loads(rec[version_num])
    
    if 'types' not in version_dict:
        raise DatabaseError()
    if type_id not in version_dict['types']:
        raise DatabaseError()
    
    for key, val in metadata.iteritems():
        version_dict['types'][type_id][key] = val
    
    insertRecord(NAMES, path, columns={version_num: json.dumps(version_dict)})
