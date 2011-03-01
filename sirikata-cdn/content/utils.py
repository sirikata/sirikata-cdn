from cassandra_storage.cassandra_util import *
import json
import time
import datetime
import operator

NAMES = getColumnFamily('Names')
FILES = getColumnFamily('Files')
NAMESBYTIME = getColumnFamily('NameTimestampIndex')

def get_content_by_date(start="", limit=25):
    try:
        index_rows = getRecord(NAMESBYTIME, 'index_rows', columns=['0'])
    except DatabaseError:
        return {}
    
    cur_index_row = index_rows[0].split(",")[-1]
    
    content_paths = getColRange(NAMESBYTIME, cur_index_row, column_start=start,
                                column_finish="", column_count=limit+1, column_reversed=True)
    
    if len(content_paths) > limit:
        oldest_timestamp = min(content_paths.keys())
        next_start = str(oldest_timestamp)
        del content_paths[oldest_timestamp]
    else:
        next_start = None
        
    content_items = []
    multiget_keys = []
    for timestamp, path in content_paths.iteritems():
        version_num = path.split("/")[-1]
        base_path = "/".join(path.split("/")[:-1])
        username = path.split("/")[1]
        multiget_keys.append(base_path)
        content_items.append({'timestamp': datetime.datetime.fromtimestamp(timestamp / 1e6),
                               'version_num': version_num,
                               'base_path': base_path,
                               'username': username,
                               'full_path': "%s/%s" % (base_path, version_num)})
    
    #TODO: This sucks. There is no way to issue a set of (rowkey, [columns]) to multiget
    # Instead, this is getting EVERY column, even though we only need the individual version
    # number for each record. This isn't TOO bad since the number of versions of each file
    # in practice will probably be low, but it's still unecessary load on the database
    name_recs = multiGetRecord(NAMES, multiget_keys)
    
    for content_item in content_items:
        name_metadata = json.loads(name_recs[content_item['base_path']][content_item['version_num']])
        content_item['metadata'] = name_metadata
        
    content_items = sorted(content_items, key=operator.itemgetter("timestamp"), reverse=True)
        
    return content_items, next_start
    

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
