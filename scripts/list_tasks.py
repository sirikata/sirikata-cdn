

import os
import sys
import argparse

def main():
    import celery.task.control
    
    for servername, tasklist in celery.task.control.inspect().active().iteritems():
        print "%s:" % servername
        for task in tasklist:
            task_id = task['id']
            name = task['name'].split(".")[-1]
            args = str(task['args'])
            print "   %s (%s) - %s" % (task_id, name, args)

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
    main()
