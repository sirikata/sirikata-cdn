import pycassa
from pycassa.system_manager import SystemManager, UTF8_TYPE
from django.core.management.base import NoArgsCommand
import cassandra_storage.settings as settings

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        sys = SystemManager(server=settings.CASSANDRA_SERVERS[0])
        REPLICATION_STRATEGY = getattr(pycassa.system_manager, settings.CASSANDRA_REPLICATION_STRATEGY)

        existing_cfs = sys.get_keyspace_column_families(settings.CASSANDRA_KEYSPACE).keys()

        if 'APIConsumers' not in existing_cfs:
            print 'Creating missing column family: APIConsumers'
            sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'APIConsumers', comparator_type=UTF8_TYPE)
            sys.alter_column(settings.CASSANDRA_KEYSPACE, 'APIConsumers', 'consumer_key', UTF8_TYPE)
            sys.alter_column(settings.CASSANDRA_KEYSPACE, 'APIConsumers', 'consumer_secret', UTF8_TYPE)
            sys.alter_column(settings.CASSANDRA_KEYSPACE, 'APIConsumers', 'username', UTF8_TYPE)

        print 'All done!'
