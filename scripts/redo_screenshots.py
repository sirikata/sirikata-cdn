import sys
import os.path
import time
from celery.execute import send_task

def do_screenshot(path, type, timestamp):
    print 'Issuing screenshot task for %s type=%s timestamp=%s' % (path, type, timestamp)
    t = send_task("celery_tasks.generate_screenshot.generate_screenshot", args=[path, type])
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
        do_screenshot(sys.argv[1], sys.argv[2], '')
    else:
        if len(sys.argv) == 2:
            next_start = sys.argv[1]
        else:
            next_start = ""
        while next_start is not None:
            content_items, next_start = get_content_by_date(next_start)
            for item in content_items:
                path = item['full_path']
                timestamp = item['full_timestamp']
                for type in item['metadata']['types'].iterkeys():
                    do_screenshot(path, type, timestamp)

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
