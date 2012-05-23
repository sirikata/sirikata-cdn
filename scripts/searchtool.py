import os
import os.path
import sys
import argparse

def list_all(args):
    results = search_index(q='*', start=0, rows=2000000)
    for result in results:
        print result['id']
        
    print
    print 'Found %d results.' % len(results)

def update_all(args):
    num_updated = update_entire_search_index()
    print '%d items updated.' % num_updated

def update_single(args):
    p = args.path
    num_updated = update_single_search_index_item(p)
    print '%d items updated.' % num_updated

def main():
    parser = argparse.ArgumentParser(description='Tool for dealing with search')
    
    subparsers = parser.add_subparsers()
    
    update_all_parser = subparsers.add_parser('update-all', help='Delete and re-index the entire search database')
    update_all_parser.set_defaults(func=update_all)
    
    update_single_parser = subparsers.add_parser('update-single', help='Update the index for a single item')
    update_single_parser.add_argument('path')
    update_single_parser.set_defaults(func=update_single)
    
    list_parser = subparsers.add_parser('list', help='Print the contents of the search database')
    list_parser.set_defaults(func=list_all)
    
    args = parser.parse_args()
    args.func(args)
    
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
    from content.utils import update_entire_search_index, search_index, update_single_search_index_item
    main()
