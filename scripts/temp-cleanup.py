import sys
import os
import json
import bsddb
import marshal

TEMP_DATA_FILE = "old_temp_data.db"

def get_data_keys():
    data_keys = set()
    for key,val in cass.getRowRange(TEMPFILES, columns=['size']):
        # Have to check for a column since deleted rows can still be returned here
        # See: http://wiki.apache.org/cassandra/FAQ#range_ghosts
        if len(val) > 0:
            data_keys.add(key)
    return data_keys

def get_referenced_keys():
    unique_keys = set()
    
    for row_key, row_data in cass.getRowRange(USERS,
                                             column_start="uploading:.",
                                             column_finish="uploading:~"):
        
        for column_key, column_data in row_data.iteritems():
            parsed_column = json.loads(column_data)
            main_rowkey = parsed_column['main_rowkey']
            unique_keys.add(main_rowkey)
            
            for subfile_name, subfile_key in parsed_column['subfiles'].iteritems():
                unique_keys.add(subfile_key)
    
    return unique_keys

def save_unused_keys(unused_keys):
    size_ct = 0
    db = bsddb.hashopen(TEMP_DATA_FILE, 'n')
    for unused_key in unused_keys:
        key_data = cass.getRecord(TEMPFILES, unused_key, column_count=10000)
        size_ct += int(key_data['size'])
        db[unused_key] = marshal.dumps(dict(key_data))
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
                print 'Writing key', previous_key, 'size', len(data)
                cass.insertRecord(TEMPFILES, previous_key, previous_data)
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
            cass.removeRecord(TEMPFILES, unused_key)
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
    
    unused_keys = data_keys.difference(referenced_keys)
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
    import cassandra_storage.cassandra_util as cass
    from celery_tasks.import_upload import get_temp_file
    TEMPFILES = cass.getColumnFamily("TempFiles")
    USERS = cass.getColumnFamily('Users')
    main()
