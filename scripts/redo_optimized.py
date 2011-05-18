import sys
import os.path
import time
from celery.execute import send_task

def do_optimized(path, type):
    print 'Issuing generate_optimized task for %s type=%s' % (path, type)
    t = send_task("celery_tasks.generate_optimized.generate_optimized", args=[path, type])
    t.wait(propagate=False)
    print 'Task finished with state %s' % t.state
    if t.state == 'FAILED':
        print 'Printing exception:'
        print
        print str(t.result)
        print
    time.sleep(1)

def main():
    if len(sys.argv) == 3:
        do_optimized(sys.argv[1], sys.argv[2])
    else:
        next_start = ""
        while next_start is not None:
            content_items, next_start = get_content_by_date(next_start)
            for item in content_items:
                path = item['full_path']
                if 'original' in item['metadata']['types']:
                    do_optimized(path, 'original')

def add_dirs():
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    upone, tail = os.path.split(thisdir)
    cdndir = os.path.join(upone, 'sirikata-cdn')
    celerydir = os.path.join(cdndir, 'celery_tasks')
    sys.path.append(cdndir)
    sys.path.append(celerydir)

if __name__ == '__main__':
    add_dirs()
    from content.utils import get_content_by_date
    main()
