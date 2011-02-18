from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django import forms
from django.http import HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages

def index(request):
    return render_to_response('content/latest.html', {}, context_instance = RequestContext(request))

class UploadForm(forms.Form):
    file = forms.FileField(required=True, widget=forms.FileInput(attrs={
        'class': '{required:true}'
    }))

class UploadResponse(forms.Form):
    title = forms.CharField(required=True, min_length=1, max_length=100, widget=forms.TextInput(attrs={
        'class': '{required:true, minlength:1, maxlength:100}'
    }))
    description = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={
        'class': '{maxlength:1000}'
    }))

def upload(request):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            upfile = request.FILES['file']
            return redirect('content.views.upload_processing')
        else:
            view_params = {'form':form}
    else:
        form = UploadForm()
        view_params = {'form':form}
    return render_to_response('content/upload.html', view_params, context_instance = RequestContext(request))

def upload_processing(request):
    return render_to_response('content/processing.html', {}, context_instance = RequestContext(request))