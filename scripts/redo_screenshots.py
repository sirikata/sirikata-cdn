import sys
import os.path
import time
from celery.execute import send_task

thisdir = os.path.dirname( os.path.realpath( __file__ ) )
upone, tail = os.path.split(thisdir)
cdndir = os.path.join(upone, 'sirikata-cdn')
celerydir = os.path.join(cdndir, 'celery_tasks')

sys.path.append(cdndir)
sys.path.append(celerydir)

from content.utils import get_content_by_date

next_start = ""
while next_start is not None:
    content_items, next_start = get_content_by_date(next_start)
    for item in content_items:
        path = item['full_path']
        type = 'original'
        print 'Issuing screenshot task for %s' % path
        t = send_task("celery_tasks.generate_screenshot.generate_screenshot", args=[path, "original"])
        t.wait()
        print 'Task finished with state %s' % t.state
        if t.state == 'FAILED':
            print 'Printing exception:'
            print
            print str(t.result)
            print
        time.sleep(1)
