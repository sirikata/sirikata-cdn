import pycassa
from pycassa.system_manager import *
from django.core.management.base import NoArgsCommand
from cassandra_storage.settings import CASSANDRA_SERVER

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        sys = SystemManager(server=CASSANDRA_SERVER)
 
        # If there is already a Sirikata-CDN keyspace, we have to ask the user
        # what they want to do with it.
        try:
            sys.get_keyspace_properties('SirikataCDN')
            # If there were a keyspace, it would have raised an exception.
            msg = 'Looks like you already have a SirikataCDN keyspace.\nDo you '
            msg += 'want to delete it and recreate it? All current data will '
            msg += 'be deleted! (y/n): '
            resp = raw_input(msg)
            if not resp or resp[0] != 'y':
                print "Ok, then we're done here."
                return
            sys.drop_keyspace('SirikataCDN')
        except pycassa.NotFoundException:
            pass
              
        sys.create_keyspace('SirikataCDN', replication_factor=1)
        sys.create_column_family('SirikataCDN', 'Users', comparator_type=UTF8_TYPE)
        sys.create_column_family('SirikataCDN', 'Names', comparator_type=UTF8_TYPE)
        sys.create_column_family('SirikataCDN', 'Files', comparator_type=BYTES_TYPE)

        print 'All done!'
