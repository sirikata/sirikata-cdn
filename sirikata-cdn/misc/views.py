from django.template import RequestContext
from django.shortcuts import render_to_response

def about(request):
    return render_to_response('misc/about.html', [], context_instance = RequestContext(request))
