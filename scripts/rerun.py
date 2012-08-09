import sys
import os
import os.path
import time
from celery.execute import send_task
import argparse

def detect_screenshot(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if 'screenshot' in metadata['types'][modeltype]:
        return True
    return False

def detect_optimized(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if 'optimized' in metadata['types']:
        return True
    return False

def detect_metadata(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if 'subfile_sizes_gzip' not in metadata['types'][modeltype]:
        return False
    if 'metadata' not in metadata['types'][modeltype]:
        return False
    meta = metadata['types'][modeltype]['metadata']
    if 'bounds_info' not in meta:
        return False
    return True

def detect_progressive_errors(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if 'progressive_perceptual_error' not in metadata['types'][modeltype]:
        return False
    return True

def detect_progressive(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if 'progressive' in metadata['types']:
        return True
    return False

def detect_panda3d(modeltype, metadata):
    if metadata is None or 'types' not in metadata or modeltype not in metadata['types']:
        return False
    if modeltype not in metadata['types']:
        return False
    if 'panda3d_base_bam' in metadata['types'][modeltype] and \
       'panda3d_full_bam' in metadata['types'][modeltype] or \
       'panda3d_bam' in metadata['types'][modeltype]:
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
         'generate_progressive_errors' :
            {'task_name': 'celery_tasks.generate_progressive_errors.generate_progressive_errors',
             'detect_func': detect_progressive_errors},
         'generate_progressive' :
            {'task_name': 'celery_tasks.generate_progressive.generate_progressive',
             'detect_func': detect_progressive},
         'generate_panda3d' :
            {'task_name': 'celery_tasks.generate_panda3d.generate_panda3d',
             'detect_func': detect_panda3d}}

class TaskInfo(object):
    def __init__(self, taskname, path, modeltype, timestamp):
        self.taskname = taskname
        self.path = path
        self.modeltype = modeltype
        self.timestamp = timestamp
    
    def __str__(self):
        return '%s task for %s type=%s timestamp=%s' % (self.taskname,
                                                        self.path,
                                                        self.modeltype,
                                                        self.timestamp)
    def __repr__(self):
        return str(self)

running_tasks = []
NUM_CONCURRENT_TASKS = None
FORCE_TASK = False
SAVE_SUCCESS = None
SAVE_FAILURE = None
EXCLUDE_EXACT = set()
EXCLUDE_IN = set()

def emit_finished_tasks():
    global running_tasks
    
    tokeep = []
    for (t, task_info) in running_tasks:
        if t.state == 'SUCCESS' or t.state == 'FAILURE':
            print 'Completed', task_info,
            print t.state
            if t.state == 'SUCCESS' and SAVE_SUCCESS is not None:
                SAVE_SUCCESS.write(task_info.path + "\n")
            if t.state == 'FAILURE':
                if SAVE_FAILURE is not None:
                    SAVE_FAILURE.write(task_info.path + "\n")
                print 'Printing failure result:'
                print
                print 'Failure type:', type(t.result)
                print 'Failure string:', str(t.result)
                print 'Traceback:', t.traceback
                print
        else:
            tokeep.append((t,task_info))
    
    running_tasks = tokeep

def wait_if_needed():
    updated = False
    while len(running_tasks) >= NUM_CONCURRENT_TASKS:
        if not updated:
            print 'Currently waiting on:'
            print '\n'.join('\t%s' % task_info for t,task_info in running_tasks)
            updated = True
        emit_finished_tasks()
        time.sleep(1)
        
def wait_all():
    while len(running_tasks) > 0:
        before = len(running_tasks)
        emit_finished_tasks()
        after = len(running_tasks)
        if after < before and after > 0:
            print 'Currently waiting on:'
            print '\n'.join('\t%s' % task_info for t,task_info in running_tasks)
        time.sleep(1)

def do_task(taskname, path, modeltype, timestamp=None, metadata=None):
    if path in EXCLUDE_EXACT:
        return
    for e in EXCLUDE_IN:
        if e in path:
            return
    
    if not FORCE_TASK and metadata is not None:
        detect_func = tasks[taskname]['detect_func']
        if detect_func(modeltype, metadata):
            return
    
    task_info = TaskInfo(taskname, path, modeltype, str(timestamp))
    print 'Issuing', task_info
    t = send_task(tasks[taskname]['task_name'], args=[path, modeltype])
    running_tasks.append((t, task_info))
    wait_if_needed()

def do_single(task, path, modeltype=None):
    metadata = get_file_metadata(path)
    if modeltype is None:
        for t in metadata['types']:
            do_task(task, path, t, metadata=metadata)
    else:
        if modeltype not in metadata['types']:
            print >> sys.stderr, 'Invalid type', modeltype, 'for path', path
            return
        do_task(task, path, modeltype, metadata=metadata)
        

def do_all(task, timestamp=None, modeltype=None):
    next_start = ""
    if timestamp is not None:
        next_start = timestamp

    while next_start is not None:
        content_items, next_start, prev_start = get_content_by_date(next_start)
        for item in content_items:
            path = item['full_path']
            timestamp = item['full_timestamp']
            for existing_type in item['metadata']['types'].iterkeys():
                if modeltype is None or modeltype == existing_type:
                    do_task(task, path, existing_type, timestamp, item['metadata'])

def do_fromfile(task, infile, modeltype=None):
    for line in infile:
        line = line.strip()
        if len(line) == 0:
            continue
        do_single(task, line, modeltype=modeltype)

def main():
    global NUM_CONCURRENT_TASKS
    global FORCE_TASK
    global SAVE_SUCCESS
    global SAVE_FAILURE
    global EXCLUDE_EXACT
    global EXCLUDE_IN
    
    parser = argparse.ArgumentParser(description='Reprocess tasks')
    parser.add_argument('--concurrency', help='number of concurrent outstanding tasks', default=1, type=int)
    parser.add_argument('--force', help='Force task to execute, even if it has already been performed', action='store_true')
    parser.add_argument('--save-success', help='Write the list of successful meshes to file', type=argparse.FileType('w'))
    parser.add_argument('--save-failure', help='Write the list of failed meshes to file', type=argparse.FileType('w'))
    parser.add_argument('--exclude-exact', type=argparse.FileType('r'), help='List of exact mesh paths to exclude, one per line')
    parser.add_argument('--exclude-in', type=argparse.FileType('r'), help='List of strings that will exclude a mesh if the string is contained in its path')
    parser.add_argument('task', help='task to execute', choices=tasks.keys())
    subparsers = parser.add_subparsers()
    
    optall = subparsers.add_parser('all', help='reprocess all')
    optall.add_argument('--type', dest='modeltype', help='only reprocess this type of all files')
    optall.add_argument('--timestamp', help='start at this timestamp')
    optall.set_defaults(func=do_all)
    
    single = subparsers.add_parser('single', help='reprocess a single file')
    single.set_defaults(func=do_single)
    single.add_argument('path')
    single.add_argument('--type', dest='modeltype', help='only reprocess this type of the file')
    
    fromfile = subparsers.add_parser('fromfile', help='reprocess models listed in given file (one per line)')
    fromfile.add_argument('infile', type=argparse.FileType('r'), help='Path to the file')
    fromfile.add_argument('--type', dest='modeltype', help='only reprocess this type of all files')
    fromfile.set_defaults(func=do_fromfile)
    
    args = parser.parse_args()
    
    NUM_CONCURRENT_TASKS = args.concurrency
    FORCE_TASK = args.force
    SAVE_SUCCESS = args.save_success
    SAVE_FAILURE = args.save_failure
    
    if args.exclude_exact is not None:
        lines = [line.strip() for line in args.exclude_exact.read().split()]
        EXCLUDE_EXACT = set([line for line in lines if len(line) > 0]) 
    
    if args.exclude_in is not None:
        lines = [line.strip() for line in args.exclude_in.read().split()]
        EXCLUDE_IN = set([line for line in lines if len(line) > 0]) 
    
    parsing_result = vars(args)
    to_execute = parsing_result['func']
    del parsing_result['func']
    del parsing_result['concurrency']
    del parsing_result['save_success']
    del parsing_result['save_failure']
    del parsing_result['exclude_exact']
    del parsing_result['exclude_in']
    del parsing_result['force']
    to_execute(**parsing_result)
    
    wait_all()

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
    from content.utils import get_content_by_date, get_file_metadata
    main()
