CASSANDRA_SERVERS = ['localhost:9160',]
"""Location and port of Cassandra's Thrift interface"""
CASSANDRA_KEYSPACE = 'SirikataCDN'
"""Keyspace to create/connect to"""
CASSANDRA_REPLICATION_FACTOR = 1
"""Replication factor for data. This should be 1 for local instances, higher for production deployments"""

"""
There are two consistency levels for cassandra configuration - (READ,WRITE).
For single server installs this should be set to (ONE,ANY). For a single datacenter
replicated install, (ONE,ANY) might lead to data loss. Instead, (QUORUM,ANY) is
safer. This could still lead to very rare inconsistent results, so (QUORUM,QUORUM)
is sufficient for strong consistency. For wide-area installs, it really depends
on your configuration. I'd suggest (LOCAL_QUORUM,LOCAL_QUORUM) for a multi-homed
website install.
"""

CASSANDRA_WRITE_CONSISTENCY = 'ANY'
"""
Possible values are:
* ANY Ensure that the write has been written once somewhere, including
  possibly being hinted in a non-target node.
* ONE Ensure that the write has been written to at least 1 node's commit
  log and memory table
* QUORUM Ensure that the write has been written to
  <ReplicationFactor> / 2 + 1 nodes
* LOCAL_QUORUM Ensure that the write has been written to
  <ReplicationFactor> / 2 + 1 nodes, within the local datacenter (requires
  NetworkTopologyStrategy)
* EACH_QUORUM Ensure that the write has been written to
  <ReplicationFactor> / 2 + 1 nodes in each datacenter (requires
  NetworkTopologyStrategy)
* ALL Ensure that the write is written to <ReplicationFactor> nodes before
  responding to the client.
"""
CASSANDRA_READ_CONSISTENCY = 'ONE'
"""
Possible values are:
* ANY Not supported. You probably want ONE instead.
* ONE Will return the record returned by the first node to respond. A
  consistency check is always done in a background thread to fix any
  consistency issues when ConsistencyLevel.ONE is used. This means subsequent
  calls will have correct data even if the initial read gets an older value.
  (This is called 'read repair'.)
* QUORUM Will query all storage nodes and return the record with the most
  recent timestamp once it has at least a majority of replicas reported.
  Again, the remaining replicas will be checked in the background.
* LOCAL_QUORUM Returns the record with the most recent timestamp once a
  majority of replicas within the local datacenter have replied.
* EACH_QUORUM Returns the record with the most recent timestamp once a
  majority of replicas within each datacenter have replied.
* ALL Queries all storage nodes and returns the record with the most recent
  timestamp.
"""
