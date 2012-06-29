from cassandra_storage.cassandra_util import *
import json
import sys
import time
import datetime
import operator
import posixpath
import pysolr
from users.middleware import remove_file_upload, save_file_upload
from django.conf import settings
from celery.execute import send_task

SOLR_URL = getattr(settings, 'SOLR_READ_URL')
SOLR_CONNECTION = None if SOLR_URL is None else pysolr.Solr(SOLR_URL)

NAMES = getColumnFamily('Names')
FILES = getColumnFamily('Files')
NAMESBYTIME = getColumnFamily('NameTimestampIndex')

class PathInfo(object):
    """Helper class for dealing with CDN paths"""
    def __init__(self, filename):
        self.filename = filename
        self.normpath = posixpath.normpath(filename)
        """Normalized original path"""
        
        split = self.normpath.split("/")
        try:
            self.version = str(int(split[-1]))
            """Version number of the path"""
        except ValueError:
            self.version = None
    
        if self.version is None:
            self.basename = split[-1]
            """The filename of the path"""
            self.basepath = self.normpath
            """The base of the path, without the version number"""
        else:
            self.basename = split[-2]
            self.basepath = '/'.join(split[:-1])
            
    def __str__(self):
        return "<PathInfo filename='%s', normpath='%s', basepath='%s', basename='%s', version='%s'>" % \
                (self.filename, self.normpath, self.basepath, self.basename, self.version)
    
    def __repr__(self):
        return str(self)

def get_model_data_from_path(path):
    version_num = path.split("/")[-1]
    base_path = "/".join(path.split("/")[:-1])
    base_name = posixpath.basename(base_path)
    prefix_path = posixpath.dirname(base_path)
    username = path.split("/")[1]
    return {
        'version_num': version_num,
        'base_path': base_path,
        'base_name': base_name,
        'prefix_path': prefix_path,
        'username': username,
        'full_path': '%s/%s' % (base_path, version_num)
    }

def get_content_by_name(names):
    name_recs = multiGetRecord(NAMES, names)
    items = []
    for name, rec in name_recs.iteritems():
        model_data = get_model_data_from_path(name)
        item = {}
        item['username'] = model_data['username']
        item['full_path'] = model_data['full_path']
        item['metadata'] = json.loads(rec[rec['latest']])
        items.append(item)
    return items

def get_content_by_date(start="", limit=25, reverse=True):
    try:
        index_rows = getRecord(NAMESBYTIME, 'index_rows', columns=[0])
    except DatabaseError:
        return {}, None, None

    cur_index_row = index_rows[0].split(",")[-1]

    if reverse:
        extra_fetch = 1
    else:
        extra_fetch = 2
        
    try:
        long_start = long(start)
    except ValueError:
        long_start = ""
    content_paths = getColRange(NAMESBYTIME, cur_index_row, column_start=long_start,
                                column_finish="", column_count=limit+extra_fetch, column_reversed=reverse)

    older_start = None
    newer_start = None

    oldest_timestamp = min(content_paths.keys())
    newest_timestamp = max(content_paths.keys())

    if reverse:
        if len(content_paths) > limit:
            older_start = str(oldest_timestamp)
            del content_paths[oldest_timestamp]
        if start != "":
            newer_start = str(newest_timestamp)
    else:
        older_start = str(oldest_timestamp)
        del content_paths[oldest_timestamp]
        if len(content_paths) > limit:
            del content_paths[newest_timestamp]
            newest_timestamp = max(content_paths.keys())
            newer_start = str(newest_timestamp)

    content_items = []
    multiget_keys = []
    for timestamp, path in content_paths.iteritems():
        model_data = get_model_data_from_path(path)
        multiget_keys.append(model_data['base_path'])
        content_items.append({'timestamp': datetime.datetime.fromtimestamp(timestamp / 1e6),
                               'full_timestamp': timestamp,
                               'version_num': model_data['version_num'],
                               'base_path': model_data['base_path'],
                               'username': model_data['username'],
                               'base_name': model_data['base_name'],
                               'prefix_path': model_data['prefix_path'],
                               'full_path': model_data['full_path']
                               })

    #TODO: This sucks. There is no way to issue a set of (rowkey, [columns]) to multiget
    # Instead, this is getting EVERY column, even though we only need the individual version
    # number for each record. This isn't TOO bad since the number of versions of each file
    # in practice will probably be low, but it's still unecessary load on the database
    name_recs = multiGetRecord(NAMES, multiget_keys)

    found_items = []
    deleted_items = []
    for content_item in content_items:
        if content_item['base_path'] in name_recs and content_item['version_num'] in name_recs[content_item['base_path']]:
            name_metadata = json.loads(name_recs[content_item['base_path']][content_item['version_num']])
            content_item['metadata'] = name_metadata
            found_items.append(content_item)
        else:
            deleted_items.append(content_item)

    #do some lazy index maintenance
    for content_item in deleted_items:
        try: removeColumns(NAMESBYTIME, cur_index_row, columns=[content_item['full_timestamp']])
        except DatabaseError: pass

    found_items = sorted(found_items, key=operator.itemgetter("timestamp"), reverse=True)

    return found_items, older_start, newer_start

def list_content(**kwargs):
    recs = getRowRange(NAMES, **kwargs)
    for r in recs:
        yield r

def get_file_metadata(filename):
    split = filename.split("/")

    version = split[-1:][0]
    file_key = "/".join(split[:-1])

    try:
        rec = getRecord(NAMES, file_key, columns=[version, "type"], include_timestamp=True)
    except DatabaseError:
        raise

    if version not in rec:
        raise NotFoundError("Given file version not found")

    version_data, timestamp = rec[version]
    version_data = json.loads(version_data)
    version_data['type'] = rec['type'][0]
    version_data['timestamp'] = timestamp
    return version_data

def update_ttl(filename, ttl):
    split = filename.split("/")

    version = split[-1:][0]
    file_key = "/".join(split[:-1])

    rec = getRecord(NAMES, file_key, columns=[version])
    insertRecord(NAMES, file_key, columns={version: rec[version]}, ttl=ttl)

def get_multi_file_metadata(filenames):
    keys = []
    for filename in filenames:
        pathinfo = PathInfo(filename)
        keys.append(pathinfo.basepath)
    
    keys = set(keys)
    recs = multiGetRecord(NAMES, keys)
    
    all_metadata = {}
    for filename in filenames:
        pathinfo = PathInfo(filename)
        if pathinfo.version is None:
            pathinfo.version = recs[pathinfo.basepath]['latest']
        
        if pathinfo.basepath not in recs or pathinfo.version not in recs[pathinfo.basepath]:
            raise NotFoundError("Specified file not found")
        
        all_metadata[filename] = json.loads(recs[pathinfo.basepath][pathinfo.version])
        all_metadata[filename]['type'] = recs[pathinfo.basepath]['type']
        
    return all_metadata

def get_hash(hash):
    try:
        rec = getRecord(FILES, hash, columns=['data', 'mimetype'])
    except:
        raise

    return rec

def multi_get_hash(hashes):
    return multiGetRecord(FILES, hashes, columns=['data', 'mimetype'])

def delete_hash(hash):
    removeRecord(FILES, hash)

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

def list_file_keys(columns=None):
    if columns is None:
        columns = []
    recs = getRowRange(FILES, columns=columns)
    for r in recs:
        yield r

def save_file_name(path, version_num, hash_key, length, ttl=None):
    dict = {'hash': hash_key, 'size': length}
    col_val = json.dumps(dict)
    insertRecord(NAMES, path, columns={version_num: col_val}, ttl=ttl)

def save_version_type(path, version_num, hash_key, length, subfile_names, zip_key, type_id, title=None, description=None, create_index=True, ttl=None):
    try:
        rec = getRecord(NAMES, path, columns=[version_num])
        version_dict = json.loads(rec[version_num])
    except NotFoundError:
        version_dict = {}

    if create_index and 'types' not in version_dict:
        create_index = True
    else:
        create_index = False

    if 'types' not in version_dict:
        version_dict['types'] = {}

    if 'title' not in version_dict:
        version_dict['title'] = title
    if 'description' not in version_dict:
        version_dict['description'] = description

    version_dict['types'][type_id] = {'hash': hash_key,
                                      'size': length,
                                      'subfiles': subfile_names,
                                      'zip': zip_key}

    insertRecord(NAMES, path, columns={version_num: json.dumps(version_dict)}, ttl=ttl)

    if create_index:
        try:
            index_rows = getRecord(NAMESBYTIME, "index_rows", columns=[0])
        except NotFoundError:
            index_rows = None

        if index_rows is None:
            insertRecord(NAMESBYTIME, "index_rows", columns={0: "0"})
            cur_index_row = "0"
        else:
            cur_index_row = index_rows[0].split(",")[-1]

        insertRecord(NAMESBYTIME, cur_index_row, {long(time.time() * 1e6) : "%s/%s" % (path, version_num)})
        
    update_single_search_index_item(path, version=version_num)

def get_new_version_from_path(path, file_type):
    try:
        rec = getRecord(NAMES, path, columns=["latest"])
        latest = str(int(rec['latest'])+1)
    except NotFoundError:
        latest = "0"

    insertRecord(NAMES, path, columns={"latest":latest, "type":file_type})

    return latest

def get_versions(path):
    try:
        rec = getRecord(NAMES, path, columns=['latest'])
        latest = int(rec['latest'])
        versions = getRecord(NAMES, path, columns=map(str, range(latest+1)))
        return list(versions.iterkeys())
    except NotFoundError:
        return None

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
    update_single_search_index_item(path, version=version_num)
    
def copy_file(frompath, fromversion, topath, updated_metadata=None):
    rec = getRecord(NAMES, frompath, columns=[fromversion, 'type'])
    version_dict = json.loads(rec[fromversion])
    file_type = rec['type']
    
    if updated_metadata:
        for key, val in updated_metadata.iteritems():
            version_dict[key] = val
    
    for type in version_dict['types']:
        prev_subfiles = version_dict['types'][type]['subfiles']
        new_subfiles = []
        for subfile in prev_subfiles:
            prev_sub_split = subfile.split('/')
            prev_sub_vers = prev_sub_split[-1]
            prev_sub_path = '/'.join(prev_sub_split[:-1])
            subrec = getRecord(NAMES, prev_sub_path, columns=['type', prev_sub_vers])
            prev_sub_path = prev_sub_path[len(frompath):]
            prev_type = subrec['type']
            new_sub_path = topath + prev_sub_path
            new_subfile_version = get_new_version_from_path(new_sub_path, file_type=prev_type)
            insertRecord(NAMES, new_sub_path, columns={new_subfile_version: subrec[prev_sub_vers]})
            new_sub_path = new_sub_path + '/' + new_subfile_version
            new_subfiles.append(new_sub_path)
        version_dict['types'][type]['subfiles'] = new_subfiles
    
    new_file_version = get_new_version_from_path(topath, file_type=file_type)
    insertRecord(NAMES, topath, columns={new_file_version: json.dumps(version_dict)})
    save_file_upload(topath.split('/')[1], topath)
    
    return topath + '/' + new_file_version
    
def add_base_metadata(path, version_num, metadata):    
    rec = getRecord(NAMES, path, columns=[version_num])
    version_dict = json.loads(rec[version_num])

    for key, val in metadata.iteritems():
        version_dict[key] = val

    insertRecord(NAMES, path, columns={version_num: json.dumps(version_dict)})
    update_single_search_index_item(path, version=version_num)

def delete_file_metadata(path, version_num):
    username = path.split("/")[1]
    remove_file_upload(username, "%s/%s" % (path, version_num))
    removeColumns(NAMES, path, columns=[version_num])
    update_single_search_index_item(path, version=version_num)

def json_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError()

def item_to_search_fields(item):
    d = { 'id': item['full_path'],
          'title': item['metadata']['title'],
          'description': item['metadata']['description'],
          'tags': item['metadata'].get('labels', []),
          'date': item['timestamp'],
          'username': item['username'],
          'metadata_json': json.dumps(item, default=json_handler),
    }
    return d

def update_single_search_index_item(path, version=None):
    if version is not None:
        path = path + '/' + version
    
    send_task("celery_tasks.search.update_single_search_index_item", args=[path])

def search_index(q='*', start=0, rows=10):
    if SOLR_CONNECTION is None:
        return []
    
    results = SOLR_CONNECTION.search(q, start=start, rows=rows)
    return results
    