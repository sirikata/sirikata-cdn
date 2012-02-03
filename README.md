Sirikata CDN Website
====================

This repository contains the files needed to host a Sirikata CDN
server. The website is written in
[Django](http://www.djangoproject.com/) but instead of using Django's
models, we use [Cassandra](http://cassandra.apache.org/) as the
database backend, interfaced with using [pycassa](https://github.com/pycassa/pycassa). [Celery](http://celeryproject.org/) is used for farming off tasks in the background, some of which use the [pycollada](https://github.com/pycollada/pycollada) library. Instead of maintaining user accounts, [python-openid](https://github.com/openid/python-openid) is used to get authentication from [OpenID](http://openid.net/) providers. [openid-selector](http://code.google.com/p/openid-selector/) is used to choose an OpenID provider.

Installation
============

See the INSTALL.md file in this directory.
