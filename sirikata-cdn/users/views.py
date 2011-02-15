from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseServerError
from django.contrib import messages
from django.core.urlresolvers import reverse

from openid.consumer.consumer import Consumer
from openid.consumer.discover import DiscoveryFailure

def login(request):
    return render_to_response('users/login.html', {}, context_instance = RequestContext(request))

def openid_select(request):
    if request.method != 'GET':
        return HttpResponseServerError("Invalid Input")
    try:
        action = request.GET['action']
        openid_identifier = request.GET['openid_identifier']
    except KeyError:
        return HttpResponseServerError("Invalid Input")
    
    if(action != 'verify'):
        return HttpResponseServerError("Invalid Input")
    
    openid_consumer = Consumer(request.session, None)
    
    try:
        auth_request = openid_consumer.begin(openid_identifier)
    except DiscoveryFailure:
        messages.error(request, 'Invalid OpenID URL')
        return redirect('users.views.login')
        
    redirect_url = auth_request.redirectURL(realm=request.build_absolute_uri('/'),
            return_to=request.build_absolute_uri(reverse('users.views.openid_return')))
        
    return redirect(redirect_url)
    
def openid_return(request):
    if request.method != 'GET':
        return HttpResponseServerError("Invalid Input")
    
    get_dict = request.GET
    base_url = request.build_absolute_uri(request.path)
    
    openid_consumer = Consumer(request.session, None)
    response = openid_consumer.complete(get_dict, base_url)
    
    if response.status != 'success':
        messages.error(request, 'Invalid OpenID URL')
        return redirect('users.views.login')
    else:
        messages.info(request, 'Nice job logging in!')
        return redirect('users.views.login')
