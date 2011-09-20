import sys
import os.path
import time
from celery.execute import send_task
import argparse

def detect_screenshot(type, metadata):
    if metadata is None or 'types' not in metadata or type not in metadata['types']:
        return False
    if 'screenshot' in metadata['types'][type]:
        return True
    return False

def detect_optimized(type, metadata):
    if metadata is None or 'types' not in metadata or type not in metadata['types']:
        return False
    if 'optimized' in metadata['types']:
        return True
    return False

def detect_metadata(type, metadata):
    if metadata is None or 'types' not in metadata or type not in metadata['types']:
        return False
    if 'metadata' in metadata['types'][type]:
        return True
    return False

def detect_progressive(type, metadata):
    if metadata is None or 'types' not in metadata or type not in metadata['types']:
        return False
    if 'progressive' in metadata['types']:
        return True
    return False

tasks = {'screenshot' :
            {'task_name': 'celery_tasks.generate_screenshot.generate_screenshot',
             'detect_func': detect_screenshot},
         'generate_optimized' :
            {'task_name': 'celery_tasks.generate_optimized.generate_optimized',
             'detect_func': detect_optimized},
         'generate_metadata' :
            {'task_name': 'celery_tasks.generate_metadata.generate_metadata',
             'detect_func': detect_metadata},
         'generate_progressive' :
            {'task_name': 'celery_tasks.generate_progressive.generate_progressive',
             'detect_func': detect_progressive}}

running_tasks = []
NUM_CONCURRENT_TASKS = None
FORCE_TASK = False

def emit_finished_tasks():
    global running_tasks
    
    tokeep = []
    for (t, task_string) in running_tasks:
        if t.state == 'SUCCESS' or t.state == 'FAILURE':
            print 'Completed', task_string,
            print t.state
            if t.state == 'FAILURE':
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

def do_task(taskname, path, type, timestamp=None, metadata=None):
    if not FORCE_TASK and metadata is not None:
        detect_func = tasks[taskname]['detect_func']
        if detect_func(type, metadata):
            return
    
    task_string = '%s task for %s type=%s timestamp=%s' % (taskname, path, type, str(timestamp))
    print 'Issuing', task_string
    t = send_task(tasks[taskname]['task_name'], args=[path, type])
    running_tasks.append((t, task_string))
    wait_if_needed()

def do_single(task, path, type=None):
    metadata = get_file_metadata(path)
    if type is None:
        for t in metadata['types']:
            do_task(task, path, t, metadata=metadata)
    else:
        if type not in metadata['types']:
            print >> sys.stderr, 'Invalid type', type, 'for path', path
            return
        do_task(task, path, type, metadata=metadata)
        

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
                    do_task(task, path, existing_type, timestamp, item['metadata'])

def main():
    global NUM_CONCURRENT_TASKS
    global FORCE_TASK
    
    parser = argparse.ArgumentParser(description='Reprocess tasks')
    parser.add_argument('--concurrency', help='number of concurrent outstanding tasks', default=1, type=int)
    parser.add_argument('--force', help='Force task to execute, even if it has already been performed', action='store_true')
    parser.add_argument('task', help='task to execute', choices=tasks.keys())
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
    FORCE_TASK = args.force
    
    parsing_result = vars(args)
    to_execute = parsing_result['func']
    del parsing_result['func']
    del parsing_result['concurrency']
    del parsing_result['force']
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
