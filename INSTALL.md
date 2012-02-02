Dependencies
============

Website
-------

* django
* thrift
* pycassa
* openid
* celery

You can install these with the webserver requirements file with this command:

    pip install -U -r requirements/webserver.txt

Celery Daemon
-------------

* collada
  * git clone git://github.com/pycollada/pycollada.git
  * python setup.py install
* meshtool
  * git clone git://github.com/pycollada/meshtool.git
  * python setup.py install
* networkx - apt-get install python-networkx
* pyopencv - pip install pyopencv
* panda3d

For Ubuntu Users
----------------

* echo "deb http://archive.panda3d.org/ubuntu maverick main" > /etc/apt/sources.list.d/panda3d.list && apt-get update
* apt-get install git cmake python-dev libboost-dev libcv-dev libboost-python-dev libhighgui-dev libcvaux-dev python-numpy python-pip python-lxml python-networkx python-imaging panda3d1.7
* cp /usr/lib/python2.6/dist-packages/panda3d.pth /usr/lib/python2.7/dist-packages/
* pip install pyopencv thrift pycassa python-openid celery django pysolr
* git clone git://github.com/pycollada/pycollada.git && pip install -e ./pycollada
* git clone git://github.com/pycollada/meshtool.git && pip install -e ./meshtool
