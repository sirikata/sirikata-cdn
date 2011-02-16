from django.template import RequestContext
from django.shortcuts import render_to_response, redirect

def index(request):
    print request.__dict__.keys()
    return render_to_response('content/latest.html', {}, context_instance = RequestContext(request))

def upload(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    return render_to_response('content/upload.html', dict, context_instance = RequestContext(request))
