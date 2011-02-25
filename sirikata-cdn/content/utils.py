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
