import oauth2
import httplib2
import urlparse
import sys
import pprint
import json
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
import urllib2
import time
import getopt
import os

#BASE_OPEN3DHUB = 'http://open3dhub.com'
BASE_OPEN3DHUB = 'http://localhost:8000' 
UPLOAD_URL = BASE_OPEN3DHUB + '/api/upload'
UPLOAD_STATUS_URL = BASE_OPEN3DHUB + '/upload/processing/%TASK_ID%?api&username=%USERNAME%'

CONSUMER_KEY = 'efgPOA8pZ3mLNNcPMzPRPwQH6zzENcOiC6bd4iklWzQ='
CONSUMER_SECRET = 'xbY2_AuwURK5pCpIU9XB6nROMofDv_O-gPdhaRsT2Mk='
ACCESS_KEY = 'IJnw5e6pxkcI-Upa3RDANjL5HUcrc10BICM7eiRh-XA='
ACCESS_SECRET = 'xCf-CtG99snn2-e1YrZHD0OR4nEW6WHjStGpU-MQKLQ='
USERNAME = 'jterrace'

# Register the poster module's streaming http handlers with urllib2
register_openers()

def printresp(resp, content):
    for header, value in resp.iteritems():
        print '%s: %s' % (header, value)
    print content
    
def exitprint(resp, content):
    printresp(resp, content)
    print "Error code: %s" % resp['status']
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print >> sys.stderr, 'Usage: python upload.py main_file [subfile1 [subfile2 ..]]'
        sys.exit(1)
    
    opts, args = getopt.getopt(sys.argv[1:], ':')
    upload_files = args
    for f in upload_files:
        if not os.path.isfile(f):
            print >> sys.stderr, 'File not found: %s' % (f,)
            sys.exit(1)
    
    consumer = oauth2.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    access_token = oauth2.Token(ACCESS_KEY, ACCESS_SECRET)
    
    main_filename = os.path.basename(upload_files[0])
    
    upload_params = dict(title = 'Test Model',
                         username = USERNAME,
                         path = 'apiupload/' + main_filename,
                         main_filename = main_filename,
                         description = 'some sphere',
                         labels = 'some stuff')
    
    req = oauth2.Request.from_consumer_and_token(consumer,
                                                 token=access_token,
                                                 http_method="POST",
                                                 http_url=UPLOAD_URL,
                                                 parameters=upload_params)

    req.sign_request(oauth2.SignatureMethod_HMAC_SHA1(), consumer, access_token)
    compiled_postdata = req.to_postdata()
    all_upload_params = urlparse.parse_qs(compiled_postdata, keep_blank_values=True)
    
    #parse_qs returns values as arrays, so convert back to strings
    for key, val in all_upload_params.iteritems():
        all_upload_params[key] = val[0]
    
    for fpath in upload_files:
        all_upload_params[os.path.basename(fpath)] = open(fpath, 'rb')
    datagen, headers = multipart_encode(all_upload_params)
    request = urllib2.Request(UPLOAD_URL, datagen, headers)
    
    try:
        respdata = urllib2.urlopen(request).read()
    except urllib2.HTTPError, ex:
        print >> sys.stderr, 'Received error code: ', ex.code
        print >> sys.stderr
        print >> sys.stderr, ex
        sys.exit(1)
        
    result = json.loads(respdata)

    if result.get('success') != True or 'task_id' not in result:
        print >> sys.stderr, 'Upload failed. Error = ', result.get('error')
        print >> sys.stderr
        sys.exit(1)
    
    task_id = result['task_id']
    print 'Succeeded in submitting upload. Task ID = %s Checking status...' % (task_id,)
    print
    
    complete = False
    toreq = UPLOAD_STATUS_URL.replace("%TASK_ID%", task_id)
    toreq = toreq.replace("%USERNAME%", USERNAME)
    h = httplib2.Http()
    while not complete:
        resp, content = h.request(toreq, "GET")
        if resp['status'] != '200':
            exitprint(resp, content)
        result = json.loads(content)
        if 'state' not in result:
            exitprint(resp, content)
        complete = (result['state'] == 'SUCCESS' or result['state'] == 'FAILURE')
        if complete == False:
            print 'Not complete. State = %s' % (result.get('state'))
        time.sleep(0.5)
        
    print
    print 'Finished. State = %s' % (result.get('state'),)
    print
    if result.get('state') == 'SUCCESS':
        print "New upload has path: '%s'" % (result.get('path'))
    
if __name__ == '__main__':
    main()