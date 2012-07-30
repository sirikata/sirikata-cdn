import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Revoke a task')
    parser.add_argument('task_id', help='Task ID to revoke')
    args = parser.parse_args()
    
    revoke(args.task_id, terminate=True)

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
    from celery.task.control import revoke
    main()
