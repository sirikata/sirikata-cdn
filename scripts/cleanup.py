import sys
import os
import json
import bsddb
import marshal

TEMP_DATA_FILE = "old_data.db"

def get_data_keys():
    data_keys = set()
    for key,val in list_file_keys(columns=['mimetype']):
        # Have to check for a column since deleted rows can still be returned here
        # See: http://wiki.apache.org/cassandra/FAQ#range_ghosts
        if len(val) > 0:
            data_keys.add(key)
    return data_keys

def get_referenced_keys():
    unique_keys = set()
    
    for key, cols in list_content():
        key_type = cols['type']
        
        for col, value in cols.iteritems():
            if col == 'latest' or col == 'type':
                continue
            
            #image files just have a single hash
            if key_type == 'image':
                value_dict = json.loads(value)
                unique_keys.add(value_dict['hash'])
                
            elif key_type == 'collada':
                value_dict = json.loads(value)
                for output_type, type_data in value_dict['types'].iteritems():
                    
                    #all of these could have a hash in them
                    hash_keys = ['zip', 'screenshot', 'hash', 'thumbnail',
                                 'progressive_stream', 'panda3d_base_bam',
                                 'panda3d_full_bam', 'panda3d_bam']
                    for hash_key in hash_keys:
                        hash_key_val = type_data.get(hash_key)
                        if hash_key_val is not None:
                            unique_keys.add(type_data[hash_key])
                            
                    #progressive mipmaps are nested
                    if 'mipmaps' in type_data:
                        for mipmap_data in type_data['mipmaps'].itervalues():
                            unique_keys.add(mipmap_data['hash'])
                
            else:
                raise Exception("Unknown file type!")
                
    return unique_keys

def save_unused_keys(unused_keys):
    size_ct = 0
    db = bsddb.hashopen(TEMP_DATA_FILE, 'n')
    for unused_key in unused_keys:
        try:
            key_data = get_hash(unused_key)
        except NotFoundError:
            key_data = ""
        size_ct += len(key_data['data'])
        unused_key = unused_key.encode('ascii')
        mimetype = key_data['mimetype'].encode('ascii')
        db[unused_key] = marshal.dumps({ 'data':key_data['data'],
                                         'mimetype':mimetype })
    db.close()
    return size_ct

def read_back_db():
    print 'CHECKING FOR PREVIOUS DB FILE'
    print '-----------------------------'
    try:
        db = bsddb.hashopen(TEMP_DATA_FILE, 'r')
    except bsddb.db.DBNoSuchFileError:
        print 'Did not find a temporary BDB file. Skipping read-back step.'
        return
    
    previous_keys = db.keys()
    print 'Found', len(previous_keys), 'keys in previous data file.'
    
    if len(previous_keys) == 0:
        print 'Since no keys in previous file, continuing.'
        return
    
    referenced_keys = get_referenced_keys()
    print 'Checking', len(referenced_keys), 'referenced keys for previous items'
    
    still_referenced = referenced_keys.intersection(previous_keys)
    print 'Found', len(still_referenced), 'keys previously deleted that are now referenced.'
    
    if len(still_referenced) == 0:
        erase_check = raw_input('No previously deleted keys are referenced. Okay to erase old db (y/n)? ')
        if erase_check.upper().strip() == 'Y':
            print 'Okay, continuing.'
            return
        else:
            print 'Okay, nothing left to do here. Exiting.'
            sys.exit(0)
    else:
        rewrite_check = raw_input('Would you like me to rewrite the %d keys (y/n)? ' % (len(still_referenced),))
        if rewrite_check.upper().strip() == 'Y':
            print 'Okay, going to write keys now.'
            for previous_key in still_referenced:
                previous_data = marshal.loads(db[previous_key])
                mimetype = previous_data['mimetype']
                data = previous_data['data']
                print 'Writing key', previous_key, 'mimetype', mimetype, 'length', len(data)
                save_file_data(previous_key, data, mimetype)
            print 'Finished writing', len(still_referenced), 'keys. Exiting'
            sys.exit(0)
        else:
            print 'Okay, nothing left to do here. Exiting.'
            sys.exit(0)

def delete_unused(unused_keys):
    delete_check = raw_input('Shall I delete %d unreferenced keys (y/n)? ' % len(unused_keys))
    if delete_check.upper().strip() == 'Y':
        print 'Okay, deleting keys...'
        for unused_key in unused_keys:
            print 'Deleting', unused_key
            delete_hash(unused_key)
        print "Finished deleting %d keys. Backup is saved at '%s' Exiting." % (len(unused_keys), TEMP_DATA_FILE)
        sys.exit(0)
    else:
        print 'Okay, nothing to do here. Exiting.'
        sys.exit(0)

def main():
    read_back_db()
    print
    
    print 'LOOKING FOR UNUSED KEYS TO CLEAN UP'
    print '-----------------------------------'
    data_keys = get_data_keys()
    print 'Found', len(data_keys), 'data keys in the database.'
    
    referenced_keys = get_referenced_keys()
    print 'Found', len(referenced_keys), 'referenced keys'
    
    unused_keys = referenced_keys.symmetric_difference(data_keys)
    print 'Found', len(unused_keys), 'unused keys that can be deleted'
    
    print 'Fetching unused keys from database and writing to temp file'
    size_ct = save_unused_keys(unused_keys)
    print 'Wrote', size_ct, 'bytes to temporary db file'
    
    if len(unused_keys) == 0:
        print 'Since no unused keys, nothing left to do. Exiting.'
        sys.exit(0)
    else:
        delete_unused(unused_keys)

def add_dirs():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    upone, tail = os.path.split(thisdir)
    cdndir = os.path.join(upone, 'sirikata-cdn')
    celerydir = os.path.join(cdndir, 'celery_tasks')
    sys.path.append(cdndir)
    sys.path.append(celerydir)

if __name__ == '__main__':
    add_dirs()
    from content.utils import list_file_keys, list_content, get_hash, save_file_data, delete_hash
    from cassandra_storage.cassandra_util import NotFoundError
    main()