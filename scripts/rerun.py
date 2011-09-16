import sys
import os.path
import time
from celery.execute import send_task
import argparse

task_names = {'screenshot' : 'celery_tasks.generate_screenshot.generate_screenshot',
              'generate_optimized' : 'celery_tasks.generate_optimized.generate_optimized',
              'generate_metadata' : 'celery_tasks.generate_metadata.generate_metadata',
              'generate_progressive' : 'celery_tasks.generate_progressive.generate_progressive'}

def do_task(taskname, path, type, timestamp=None):
    print 'Issuing %s task for %s type=%s timestamp=%s...' % (taskname, path, type, str(timestamp)),
    sys.stdout.flush()
    t = send_task(task_names[taskname], args=[path, type])
    t.wait(propagate=False)
    print t.state
    if t.state == 'FAILED':
        print 'Printing exception:'
        print
        print str(t.result)
        print
    time.sleep(1)

def do_single(task, path, type=None):
    metadata = get_file_metadata(path)
    types_to_do = []
    if type is None:
        for type in metadata['types']:
            types_to_do.append(type)
    else:
        if type not in metadata['types']:
            print >> sys.stderr, 'Invalid type', type, 'for path', path
            return
        types_to_do.append(type)
    
    for type in types_to_do:
        do_task(task, path, type)

def do_all(task, timestamp=None, type=None):
    next_start = ""
    if timestamp is not None:
        next_start = timestamp

    while next_start is not None:
        content_items, next_start, prev_start = get_content_by_date(next_start)
        for item in content_items:
            path = item['full_path']
            timestamp = item['full_timestamp']
            for existing_type in item['metadata']['types'].iterkeys():
                if type is None or type == existing_type:
                    do_task(task, path, existing_type, timestamp)

def main():
    parser = argparse.ArgumentParser(description='Reprocess tasks')
    parser.add_argument('task', help='task to execute', choices=task_names.keys())
    subparsers = parser.add_subparsers()
    all = subparsers.add_parser('all', help='reprocess all')
    all.add_argument('--type', help='only reprocess this type of all files')
    all.add_argument('--timestamp', help='start at this timestamp')
    all.set_defaults(func=do_all)
    single = subparsers.add_parser('single', help='reprocess a single file')
    single.set_defaults(func=do_single)
    single.add_argument('path')
    single.add_argument('--type', help='only reprocess this type of the file')
    
    args = parser.parse_args()
    parsing_result = vars(args)
    to_execute = parsing_result['func']
    del parsing_result['func']
    to_execute(**parsing_result)

def add_dirs():
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    upone, tail = os.path.split(thisdir)
    cdndir = os.path.join(upone, 'sirikata-cdn')
    celerydir = os.path.join(cdndir, 'celery_tasks')
    sys.path.append(cdndir)
    sys.path.append(celerydir)

if __name__ == '__main__':
    add_dirs()
    from content.utils import get_content_by_date, get_file_metadata
    main()
