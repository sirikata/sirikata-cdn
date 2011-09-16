import sys
import os.path
import time
from celery.execute import send_task
import argparse

task_names = {'screenshot' : 'celery_tasks.generate_screenshot.generate_screenshot',
              'generate_optimized' : 'celery_tasks.generate_optimized.generate_optimized',
              'generate_metadata' : 'celery_tasks.generate_metadata.generate_metadata',
              'generate_progressive' : 'celery_tasks.generate_progressive.generate_progressive'}

running_tasks = []
NUM_CONCURRENT_TASKS = None

def emit_finished_tasks():
    global running_tasks
    
    tokeep = []
    for (t, task_string) in running_tasks:
        if t.state == 'SUCCESS' or t.state == 'FAILURE':
            print 'Completed', task_string,
            print t.state
            if t.state == 'FAILED':
                print 'Printing exception:'
                print
                print str(t.result)
                print
        else:
            tokeep.append((t,task_string))
    
    running_tasks = tokeep

def wait_if_needed():
    while len(running_tasks) >= NUM_CONCURRENT_TASKS:
        emit_finished_tasks()
        time.sleep(1)
        
def wait_all():
    while len(running_tasks) > 0:
        emit_finished_tasks()
        time.sleep(1)

def do_task(taskname, path, type, timestamp=None):
    task_string = '%s task for %s type=%s timestamp=%s' % (taskname, path, type, str(timestamp))
    print 'Issuing', task_string
    t = send_task(task_names[taskname], args=[path, type])
    running_tasks.append((t, task_string))
    wait_if_needed()

def do_single(task, path, type=None):
    metadata = get_file_metadata(path)
    types_to_do = []
    if type is None:
        for t in metadata['types']:
            types_to_do.append(t)
    else:
        if type not in metadata['types']:
            print >> sys.stderr, 'Invalid type', type, 'for path', path
            return
        types_to_do.append(type)
    
    for t in types_to_do:
        do_task(task, path, t)

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
    global NUM_CONCURRENT_TASKS
    
    parser = argparse.ArgumentParser(description='Reprocess tasks')
    parser.add_argument('--concurrency', help='number of concurrent outstanding tasks', default=1, type=int)
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
    
    NUM_CONCURRENT_TASKS = args.concurrency
    
    parsing_result = vars(args)
    to_execute = parsing_result['func']
    del parsing_result['func']
    del parsing_result['concurrency']
    to_execute(**parsing_result)
    
    wait_all()

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
