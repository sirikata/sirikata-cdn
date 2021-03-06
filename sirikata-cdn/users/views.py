from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseServerError, HttpResponseNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from openid.consumer.consumer import Consumer
from openid.consumer.discover import DiscoveryFailure
import openid.extensions.ax as ax
from openid import oidutil
from cassandra_storage.cassandra_openid import CassandraStore
from middleware import login_with_openid_identity, associate_openid_login, add_user_metadata
from middleware import logout_user, get_pending_uploads, get_uploads, get_user_by_username
from middleware import add_api_consumer, remove_api_consumer
import base64
import os

#Mutes the logging output from openid. Otherwise it prints to stderr
def dummyOpenIdLoggingFunction(message, level=0):
    pass

def login(request):
    return render_to_response('users/login.html', {}, context_instance = RequestContext(request))

def logout(request):
    logout_user(request)
    return redirect('content.views.browse')

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

    realm = settings.OPENID_REALM
    redirect_url = auth_request.redirectURL(realm=realm,
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

    if login_with_openid_identity(request, response.identity_url):
        return redirect('content.views.browse')

    ax_resp = ax.FetchResponse.fromSuccessResponse(response)

    if ax_resp:
        try:
            email = ax_resp.get('http://axschema.org/contact/email')[0]
        except KeyError:
            email = ''
    
        try:
            first_name = ax_resp.get('http://axschema.org/namePerson/first')[0]
        except KeyError:
            first_name = None
    
        try:
            last_name = ax_resp.get('http://axschema.org/namePerson/last')[0]
        except KeyError:
            last_name = None

    else:
        first_name = None
        last_name = None
        email = ''

    if first_name == None and last_name == None:
        name = ''
    elif first_name == None:
        name = last_name
    elif last_name == None:
        name = first_name
    else:
        name = "%s %s" % (first_name, last_name)

    request.session['openid_identity'] = response.identity_url
    request.session['openid_email'] = email
    request.session['openid_name'] = name

    return redirect('users.views.openid_link')

def validateAlphaNumeric(value):
    if not value.isalnum():
        raise ValidationError('Username can only contain letters and numbers')

class OpenIdLinkForm(forms.Form):
    username = forms.CharField(required=True, min_length=3, max_length=50, widget=forms.TextInput(attrs={
        'class': '{required:true, minlength:3, maxlength:50}'
    }), validators=[validateAlphaNumeric])
    name = forms.CharField(required=True, min_length=1, max_length=100, widget=forms.TextInput(attrs={
        'class': '{required:true, minlength:1, maxlength:100}'
    }))
    email = forms.EmailField(required=True, min_length=3, max_length=100, widget=forms.TextInput(attrs={
        'class': '{required:true, minlength:3, maxlength:100, email:true}'
    }))

def openid_link(request):
    try:
        openid_identity = request.session['openid_identity']
        email = request.session['openid_email']
        name = request.session['openid_name']
    except KeyError:
        return HttpResponseServerError("Invalid Input")

    if request.method == 'POST':
        form = OpenIdLinkForm(request.POST)
        if form.is_valid():
            associated = associate_openid_login(request, openid_identity, email, name,
                                form.cleaned_data['username'], form.cleaned_data['email'], form.cleaned_data['name'])
            if not associated:
                messages.error(request, 'Could not associate username. This usually means the username is already taken')
                view_params = {'form':form, 'openid_identity':openid_identity}
            else:
                return redirect('content.views.browse')
        else:
            view_params = {'form':form, 'openid_identity':openid_identity}
    else:
        username = filter(lambda c: c.isalnum(), email.split('@')[0])
        form_fields = {'email':email,
                       'name':name,
                       'username':username}
        form = OpenIdLinkForm(form_fields)
        view_params = {'form':form, 'openid_identity':openid_identity}

    return render_to_response('users/openid_link.html', view_params, context_instance = RequestContext(request))

def uploads(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    pending = get_pending_uploads(request.session['username'])
    uploaded = get_uploads(request.session['username'])
    view_params = {'pending':pending, 'uploaded':uploaded}
    return render_to_response('users/uploads.html', view_params, context_instance = RequestContext(request))


def profile(request, username=""):
    user = get_user_by_username(username)
    if not user:
        return HttpResponseNotFound()

    view_params = {
        'username': username,
        'uploaded': get_uploads(username)
    }
    return render_to_response('users/profile.html', view_params, context_instance = RequestContext(request))

def remove_access_token(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    username = request.session['username']
    add_user_metadata(request, username,
                      access_token='',
                      access_secret='')
    
    return redirect('users.views.profile', username=request.session['username'])

def generate_access_token(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    username = request.session['username']
    add_user_metadata(request, username,
                      access_token=base64.urlsafe_b64encode(os.urandom(32)),
                      access_secret=base64.urlsafe_b64encode(os.urandom(32)))
    
    return redirect('users.views.profile', username=request.session['username'])

def remove_consumer_token(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    remove_api_consumer(request)
    
    return redirect('users.views.profile', username=request.session['username'])

def generate_consumer_token(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    consumer_key = base64.urlsafe_b64encode(os.urandom(32))
    consumer_secret = base64.urlsafe_b64encode(os.urandom(32))
    username = request.session['username']
    
    add_api_consumer(request, username, consumer_key, consumer_secret)
    
    return redirect('users.views.profile', username=request.session['username'])
    