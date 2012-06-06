Dependencies
============

Website
-------

* django
* thrift
* pycassa
* openid
* celery
* rabbitmq
* oauth2

You can install these with the webserver requirements file with this command:

    pip install -U -r requirements/webserver.txt

Celery Daemon
-------------

* rabbitmq - apt-get install rabbitmq-server
* collada
  * pip install -U git+git://github.com/pycollada/pycollada.git

  Or

  * git clone git://github.com/pycollada/pycollada.git
  * python setup.py install
* meshtool
  * pip install -U git+git://github.com/pycollada/meshtool.git

  Or

  * git clone git://github.com/pycollada/meshtool.git
  * python setup.py install
* networkx - apt-get install python-networkx
* pyopencv - pip install pyopencv
* panda3d

For Ubuntu Users
----------------

* Install cassandra, following http://wiki.apache.org/cassandra/DebianPackaging
  Make sure you use 10x rather than something newer as that's the current version
  we guarantee compatibility with.
* Add the Panda3D package repository (replacing 'maverick' with your
  release): echo "deb http://archive.panda3d.org/ubuntu maverick main"
  > /etc/apt/sources.list.d/panda3d.list && apt-get update
* apt-get install git cmake python-dev libboost-dev libcv-dev
  libboost-python-dev libhighgui-dev libcvaux-dev python-numpy
  python-pip python-lxml python-networkx python-imaging panda3d1.7
  rabbitmq-server
* cp /usr/lib/python2.6/dist-packages/panda3d.pth /usr/lib/python2.7/dist-packages/
* pip install pyopencv thrift pycassa python-openid celery django pysolr
* git clone git://github.com/pycollada/pycollada.git && pip install -e ./pycollada
* git clone git://github.com/pycollada/meshtool.git && pip install -e ./meshtool

If you encounter errors, make sure you don't have system packages of
the packages installed via pip, e.g. the python-django
package. Depending on the Ubuntu release, these packages may be too
old to run sirikata-cdn.

Setup
=====

*  Customize settings scripts: sirikata-cdn/settings.py,
   sirikata-cdn/cassandra_storage/settings.py, and
   sirikata-cdn/celery_tasks/celeryconfig.py

*  Setup the Cassandra schema:

        python sirikata-cdn/manage.py sync_cassandra
        python sirikata-cdn/manage.py add_newtables

*  Make sure you have Cassandra running.

*  Setup rabbitmq to communicate with Celery:

        sudo rabbitmqctl add_user jeff 12345678
        sudo rabbitmqctl add_vhost jeffhost
        sudo rabbitmqctl set_permissions -p jeffhost jeff ".*" ".*" ".*"

    These match the settings in
    sirikata-cdn/celery_tasks/celeryconfig.example.py, but you'll want
    to customize them for your setup.

*  Run Celery with the configuration

        cd sirikata-cdn
        celeryd --maxtasksperchild=1 --concurrency=1 --loglevel=DEBUG --config=celery_tasks.celeryconfig

    Note: If you set CASSANDRA_SERVERS in celeryconfig.py to not use
    localhost, you may need to add the following if you get an error
    with celery putting results into Cassandra:

        CASSANDRA_OPTIONS = {
            'server_list': ["your_host_name:9160"],
            'pool_size': 1
        }


* Run the Django test server and access the site at
  http://localhost:8000:

        python sirikata-cdn/manage.py runserver --settings=sirikata-cdn.settings

Notes
=====

* Cassandra can eat up a lot of memory with its default configuration,
  and often won't play well with other services because of this.
  Especially for development, you'll probably want to adjust its memory
  settings. These are some usable values for development:

        MAX_HEAP_SIZE="200M"
        HEAP_NEWSIZE="50M"
        flush_largest_memtables_at: 0.2
        reduce_cache_sizes_at: 0.3
        reduce_cache_capacity_to: 0.1

* To support large objects in Cassandra, adjust these values:

        thrift_framed_transport_size_in_mb: 90
        thrift_max_message_length_in_mb: 100
