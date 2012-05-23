Setting up Solr
===============

 * apt-get install solr-jetty
 * Open /etc/default/jetty in your favorite text editor
   - Change ``NO_START`` to ``0``
 * Back up the schema.xml that comes with the package:
   ``mv /etc/solr/conf/schema.xml /etc/solr/conf/schema.xml.orig``
 * Copy the sirikata CDN schema.xml to solr config:
   ``sudo cp solr/schema.xml /etc/solr/conf/``
 * Run ``/etc/init.d/jetty start`` and the server should now be accessible at
   http://localhost:8080/solr/
 * Set ``SOLR_URL`` in settings.py to ``'http://localhost:8080/solr/'``
