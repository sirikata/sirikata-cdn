from cassandra_storage.cassandra_util import *
import json
import time
import datetime
import operator
import posixpath
import pysolr
from users.middleware import remove_file_upload

SOLR_URL = 'http://localhost:8983/solandra/SirikataCDN'

NAMES = getColumnFamily('Names')
FILES = getColumnFamily('Files')
NAMESBYTIME = getColumnFamily('NameTimestampIndex')

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
        index_rows = getRecord(NAMESBYTIME, 'index_rows', columns=['0'])
    except DatabaseError:
        return {}, None

    cur_index_row = index_rows[0].split(",")[-1]

    if reverse:
        extra_fetch = 1
    else:
        extra_fetch = 2
    content_paths = getColRange(NAMESBYTIME, cur_index_row, column_start=start,
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

    # Add to solandra index.
    for item in found_items:
        solr = pysolr.Solr(SOLR_URL)
        solr.add([{
            'id': item['base_path'],
            'title': item['metadata']['title'],
            'description': item['metadata']['description'],
            'author': item['username'],
            'date': item['timestamp'],
            'tags': item['metadata'].get('labels', []),
        }])

    found_items = sorted(found_items, key=operator.itemgetter("timestamp"), reverse=True)

    return found_items, older_start, newer_start


def get_file_metadata(filename):
    split = filename.split("/")

    version = split[-1:][0]
    file_key = "/".join(split[:-1])

    try:
        rec = getRecord(NAMES, file_key, columns=[version, "type"])
    except DatabaseError:
        raise

    if version not in rec:
        raise NotFoundError("Given file version not found")

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

def save_file_name(path, version_num, hash_key, length):
    dict = {'hash': hash_key, 'size': length}
    col_val = json.dumps(dict)
    insertRecord(NAMES, path, columns={version_num: col_val})

def save_version_type(path, version_num, hash_key, length, subfile_names, zip_key, type_id, title=None, description=None):
    try:
        rec = getRecord(NAMES, path, columns=[version_num])
        version_dict = json.loads(rec[version_num])
    except NotFoundError:
        version_dict = {}

    create_index = False
    if 'types' not in version_dict:
        version_dict['types'] = {}
        create_index = True

    if 'title' not in version_dict:
        version_dict['title'] = title
    if 'description' not in version_dict:
        version_dict['description'] = description

    version_dict['types'][type_id] = {'hash': hash_key,
                                      'size': length,
                                      'subfiles': subfile_names,
                                      'zip': zip_key}

    insertRecord(NAMES, path, columns={version_num: json.dumps(version_dict)})

    if create_index:
        try:
            index_rows = getRecord(NAMESBYTIME, "index_rows", columns=['0'])
        except NotFoundError:
            index_rows = None

        if index_rows is None:
            insertRecord(NAMESBYTIME, "index_rows", columns={"0": "0"})
            cur_index_row = "0"
        else:
            cur_index_row = index_rows[0].split(",")[-1]

        insertRecord(NAMESBYTIME, cur_index_row, {long(time.time() * 1e6) : "%s/%s" % (path, version_num)})

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

def add_base_metadata(path, version_num, metadata):
    rec = getRecord(NAMES, path, columns=[version_num])
    version_dict = json.loads(rec[version_num])

    for key, val in metadata.iteritems():
        version_dict[key] = val

    insertRecord(NAMES, path, columns={version_num: json.dumps(version_dict)})

def delete_file_metadata(path, version_num):
    username = path.split("/")[1]
    remove_file_upload(username, "%s/%s" % (path, version_num))
    removeColumns(NAMES, path, columns=[version_num])

def user_search(query):
    if query == '':
        return []
    solr = pysolr.Solr(SOLR_URL)
    args = {
        'defType': 'dismax',
        'qf': r'title^3.0 description author^1.5 tags^2.0 date'
    }
    results = solr.search(query, **args)
    return [result for result in results]
