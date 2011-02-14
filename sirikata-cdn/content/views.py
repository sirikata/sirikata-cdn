from django.template import RequestContext
from django.shortcuts import render_to_response

def index(request):
    return render_to_response('content/latest.html', {}, context_instance = RequestContext(request))

def upload(request):
    dict = {}
    if request.user['is_authenticated']:
        dict['loggedin'] = 'Yes'
    else:
        dict['loggedin'] = 'No'
    return render_to_response('content/upload.html', dict, context_instance = RequestContext(request))
