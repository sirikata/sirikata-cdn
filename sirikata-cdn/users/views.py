from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseServerError
from django.contrib import messages
from django.core.urlresolvers import reverse

from openid.consumer.consumer import Consumer
from openid.consumer.discover import DiscoveryFailure
import openid.extensions.ax as ax
from openid import oidutil
from cassandra_storage.cassandra_openid import CassandraStore

#Mutes the logging output from openid. Otherwise it prints to stderr
def dummyOpenIdLoggingFunction(message, level=0):
    pass

def login(request):
    return render_to_response('users/login.html', {}, context_instance = RequestContext(request))

def openid_select(request):
    oidutil.log = dummyOpenIdLoggingFunction
    
    if request.method != 'GET':
        return HttpResponseServerError("Invalid Input")
    try:
        action = request.GET['action']
        openid_identifier = request.GET['openid_identifier']
    except KeyError:
        return HttpResponseServerError("Invalid Input")
    
    if(action != 'verify'):
        return HttpResponseServerError("Invalid Input")
    
    openid_consumer = Consumer(request.session, CassandraStore())
    
    try:
        auth_request = openid_consumer.begin(openid_identifier)
    except DiscoveryFailure:
        messages.error(request, 'Invalid OpenID URL')
        return redirect('users.views.login')
        
    ax_req = ax.FetchRequest()
    ax_req.add(ax.AttrInfo('http://axschema.org/contact/email', alias='email', required=True))
    ax_req.add(ax.AttrInfo('http://axschema.org/namePerson/first', alias='firstname', required=True))
    ax_req.add(ax.AttrInfo('http://axschema.org/namePerson/last', alias='lastname', required=True))
        
    auth_request.addExtension(ax_req)
        
    redirect_url = auth_request.redirectURL(realm=request.build_absolute_uri('/'),
            return_to=request.build_absolute_uri(reverse('users.views.openid_return')))
        
    return redirect(redirect_url)
    
def openid_return(request):
    oidutil.log = dummyOpenIdLoggingFunction
    
    if request.method != 'GET':
        return HttpResponseServerError("Invalid Input")
    
    get_dict = request.GET
    base_url = request.build_absolute_uri(request.path)
    
    openid_consumer = Consumer(request.session, CassandraStore())
    response = openid_consumer.complete(get_dict, base_url)
    
    if response.status != 'success':
        messages.error(request, 'Failed response from OpenID Provider')
        return redirect('users.views.login')
    
    ax_resp = ax.FetchResponse.fromSuccessResponse(response)
    if not ax_resp:
        messages.error(request, 'Could not get attributes from OpenID Provider')
        return redirect('users.views.login')
    
    try:
        email = ax_resp.get('http://axschema.org/contact/email')[0]
    except KeyError:
        messages.error(request, 'Could not get attributes from OpenID Provider')
        return redirect('users.views.login')
        
    try:
        first_name = ax_resp.get('http://axschema.org/namePerson/first')[0]
    except KeyError:
        first_name = None
        
    try:
        last_name = ax_resp.get('http://axschema.org/namePerson/last')[0]
    except KeyError:
        last_name = None

    if first_name == None and last_name == None:
        name = ''
    elif first_name == None:
        name = last_name
    elif last_name == None:
        name = first_name
    else:
        name = "%s %s" % (first_name, last_name)

    messages.info(request, 'email:%s name:%s url:%s' % (email, name, response.identity_url))
    return redirect('users.views.login')
