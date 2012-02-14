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
API_MODELINFO_URL = BASE_OPEN3DHUB + '/api/modelinfo%(path)s'
KEEPALIVE_URL = BASE_OPEN3DHUB + '/api/keepalive%(path)s?username=%(username)s&ttl=%(ttl)d'

CONSUMER_KEY = 'lVk5aGvdzZpVP4oh34gE80qB6KW67LfJaBQBD9BB2ec='
CONSUMER_SECRET = 'ozOvBjola-tHytqR2bpsZOskyIGGy53_MOqKrRvKQIA='
ACCESS_KEY = 'xzLvHwiPw29qjVCiy2PtZtLgN4md99ocMm8RRVJ0Zv8='
ACCESS_SECRET = 'O4hH8KDZSoTjCoHeeRtGgMUcau8M6kxtrVbJ8cM5FVY='
USERNAME = 'jterrace'
TTL_TIME = 60

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
    if len(sys.argv) < 2 or len(sys.argv) % 2 != 0:
        print >> sys.stderr, 'Usage: python ephemeral.py main_file [subfile1name subfile1path ...]'
        sys.exit(1)
    
    opts, args = getopt.getopt(sys.argv[1:], ':')
    upload_files = [args[0]]
    main_filename = os.path.basename(args[0])
    
    subfile_map = {}
    for (name, path) in zip(args[1::2], args[2::2]):
        subfile_map[name] = path
    
    consumer = oauth2.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    access_token = oauth2.Token(ACCESS_KEY, ACCESS_SECRET)
    
    upload_params = dict(title = 'Test Model',
                         username = USERNAME,
                         path = 'apiupload/' + main_filename,
                         main_filename = main_filename,
                         subfiles = json.dumps(subfile_map),
                         ephemeral = '1',
                         ttl_time = str(TTL_TIME),
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
    else:
        sys.exit(1)
        
    uploaded_path = result.get('path')
    json_info_url = API_MODELINFO_URL % {'path': uploaded_path}
    start_time = time.time()
    
    print
    print 'Checking that model is accessible via API for the TTL duration'
    print
    
    half_updated = False
    
    while time.time() - start_time < TTL_TIME * 1.5:
        
        if not half_updated and time.time() - start_time > TTL_TIME / 2.0:
            print
            print 'Updating TTL value by 50%'
            print
            
            toget = KEEPALIVE_URL % {'path': uploaded_path,
                                     'username': USERNAME,
                                     'ttl': TTL_TIME}

            client = oauth2.Client(consumer, token=access_token)
            resp, content = client.request(toget, method='GET')
            
            if resp['status'] != '200':
                print 'Updating TTL failed'
                exitprint(resp, content)
                
            print
            print 'Updating TTL by 50% success'
            print
            
            half_updated = True
        
        resp, content = h.request(json_info_url, "GET")
        if resp['status'] != '200':
            exitprint(resp, content)
        result = json.loads(content)
        if 'fullpath' not in result or result['fullpath'] != uploaded_path[1:]:
            print 'Got wrong path in API request'
            exitprint(resp, content)
        print 'Model still there... %d seconds left' % int(start_time + TTL_TIME * 1.5 - time.time())
        time.sleep(5)
        
    print
    print 'Finished checking model was still there. Waiting 20 seconds grace time...'
    print
    time.sleep(20)
    
    print
    print 'Checking that model no longer exists'
    print
    resp, content = h.request(json_info_url, "GET")
    if resp['status'] != '404':
        exitprint(resp, content)
        
    print
    print 'After TTL expired, API is now returning 404, the correct result. Done.'
    print
    
if __name__ == '__main__':
    main()
