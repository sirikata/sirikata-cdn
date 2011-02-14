Sirikata CDN Website
====================

This repository contains the files needed to host a Sirikata CDN
server. The website is written in
[Django](http://www.djangoproject.com/) but instead of using Django's
models, we use [Cassandra](http://cassandra.apache.org/) as the
database backend.

Installation
============
1. First, get the code and initialize the submodules:
    > git clone git://github.com/sirikata/sirikata-cdn.git
    > cd sirikata-cdn
    > git submodule init
    > git submodule update
2. Next, set up Cassandra. See http://cassandra.apache.org/
3. Make sure you have pycassa working:
    > cd externals/pycassa
    > python setup.py install
4. Make sure you have thrift05 installed:
    > easy_install thrift05
5. Edit sirikata-cdn/settings.py:
    * SECRET_KEY: Randomly generate this. See Django docs for more info.
6. Edit sirikata-cdn/cassandra_storage/settings.py:
    * CASSANDRA_SERVER: The host and port of Cassandra
7. Next, set up the CDN's Cassandra schema:
    > cd sirikata-cdn
    > python manage.py sync_cassandra
8. Configure a web server. See Django docs for how to do this.
