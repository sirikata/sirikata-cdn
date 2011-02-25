from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django import forms
from django.http import HttpResponseServerError, HttpResponseForbidden, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.urlresolvers import reverse
import re

from users.middleware import save_upload_task, get_pending_upload, \
                             remove_pending_upload, save_file_upload

from content.utils import get_file_metadata, get_hash

from celery_tasks.import_upload import import_upload, place_upload
from celery_tasks.import_upload import ColladaError, DatabaseError, NoDaeFound
from celery_tasks import app

from celery.execute import send_task
from celery.result import AsyncResult

def index(request):
    return render_to_response('content/latest.html', {}, context_instance = RequestContext(request))


class UploadChoiceForm(forms.Form):
    def __init__(self, task_id, choices, *args, **kwargs):
        super(UploadChoiceForm, self).__init__(*args, **kwargs)
        self.fields['file'] = forms.ChoiceField(choices=[(str(i),c) for i,c in enumerate(choices)],
                                                required=True, widget=forms.Select(attrs={
            'class': '{required:true}'
        }))

def upload_choice(request, task_id):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')

    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseForbidden
    res = AsyncResult(task_id)
    if res.state == "FAILURE" and type(res.result).__name__ == "TooManyDaeFound":
        names = res.result.names
    else:
        return HttpResponseForbidden
    
    if request.method == 'POST':
        form = UploadChoiceForm(task_id, names, request.POST)
        if form.is_valid():
            selected_dae = form.cleaned_data['file']
            for id,value in form.fields['file'].choices:
                if id == selected_dae:
                    selected_name = value
                    
            task = import_upload.delay(upload_rec['main_rowkey'], upload_rec['subfiles'], selected_name)
            
            save_upload_task(username=request.session['username'],
                             task_id=task.task_id,
                             row_key=upload_rec['main_rowkey'],
                             filename=upload_rec['filename'],
                             subfiles=upload_rec['subfiles'],
                             dae_choice=selected_name,
                             task_name="import_upload")

            try:
                remove_pending_upload(request.session['username'], task_id)
            except:
                return HttpResponseServerError("There was an error removing your old upload record.")
            
            return redirect('content.views.upload_processing', task_id=task.task_id)
    else:
        form = UploadChoiceForm(task_id, names)
    
    view_params = {'task_id':task_id, 'form':form}
    
    return render_to_response('content/upload_choice.html', view_params, context_instance = RequestContext(request))

class UploadForm(forms.Form):
    def __init__(self, file_names=['File'], *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        for f in file_names:
            self.fields[f] = forms.FileField(label=f, required=True, widget=forms.FileInput(attrs={
                'class': '{required:true}'
            }))

def upload(request, task_id=None):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    if task_id:
        try:
            upload_rec = get_pending_upload(request.session['username'], task_id)
        except:
            return HttpResponseForbidden
        orig_name = upload_rec['filename']
        subfiles_uploaded = upload_rec['subfiles']
        existing_files = subfiles_uploaded.keys()
        existing_files.append(orig_name)
        res = AsyncResult(task_id)
        if res.state == "FAILURE" and type(res.result).__name__ == "SubFilesNotFound":
            names = res.result.names
        else:
            return HttpResponseForbidden
    
    if request.method == 'POST':
        if task_id:
            form = UploadForm(names, request.POST, request.FILES)
            if form.is_valid():
                subfiles = subfiles_uploaded
                for n in names:
                    subfiles[n] = request.FILES[n].row_key
                    
                task = import_upload.delay(upload_rec['main_rowkey'], subfiles, upload_rec['dae_choice'])

                save_upload_task(username=request.session['username'],
                                 task_id=task.task_id,
                                 row_key=upload_rec['main_rowkey'],
                                 filename=upload_rec['filename'],
                                 subfiles=subfiles,
                                 dae_choice=upload_rec['dae_choice'],
                                 task_name="import_upload")

                try:
                    remove_pending_upload(request.session['username'], task_id)
                except:
                    return HttpResponseServerError("There was an error removing your old upload record.")
                
                return redirect('content.views.upload_processing', task_id=task.task_id)
                
            else:
                view_params = {'form':form, 'existing_files':existing_files}
        else:
            form = UploadForm(['File'], request.POST, request.FILES)
            if form.is_valid():
                upfile = request.FILES['File']
                task = import_upload.delay(upfile.row_key, subfiles={})
                
                save_upload_task(username=request.session['username'],
                                 task_id=task.task_id,
                                 row_key=upfile.row_key,
                                 filename=upfile.name,
                                 subfiles={},
                                 dae_choice="",
                                 task_name="import_upload")
                
                return redirect('content.views.upload_processing', task_id=task.task_id)
            else:
                view_params = {'form':form}
    else:
        if task_id:
            form = UploadForm(names)
            view_params = {'form':form, 'existing_files':existing_files}
        else:
            form = UploadForm(['File'])
            view_params = {'form':form}
            
    view_params['task_id'] = task_id
    return render_to_response('content/upload.html', view_params, context_instance = RequestContext(request))

def upload_processing(request, task_id='', action=False):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseForbidden
    
    res = AsyncResult(task_id)
    
    if action == 'confirm':
        if upload_rec['task_name'] == 'import_upload':
            try:
                remove_pending_upload(request.session['username'], task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
            messages.info(request, 'Upload removed')
            return redirect('users.views.uploads')
        else:
            path = res.result
            try:
                save_file_upload(request.session['username'], path)
            except:
                return HttpResponseServerError("There was an error saving your upload.")
            try:
                remove_pending_upload(request.session['username'], task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
            messages.info(request, 'Upload saved')
            return redirect('users.views.uploads')
            
    erase = False
    edit_link = False
    error_message = None
    success_message = None
    if res.state == "FAILURE":
        if type(res.result).__name__ == "DatabaseError":
            error_message = "An error occurred when accessing the database."
            erase = True
        elif type(res.result).__name__ == "NoDaeFound":
            error_message = "No DAE file was found in the uploaded archive."
            erase = True
        elif type(res.result).__name__ == "ColladaError":
            error_message = "There was an error parsing the collada file: %s" % str(res.result.orig)
            erase = True
        elif type(res.result).__name__ == "ImageError":
            error_message = "There was an error loading the included texture image: %s" % str(res.result.filename)
            erase = True
        elif type(res.result).__name__ == "TooManyDaeFound":
            error_message = "There is more than one DAE file in the uploaded archive. Click 'Continue' to choose one."
            edit_link = reverse('content.views.upload_choice', args=[task_id])
        elif type(res.result).__name__ == "SubFilesNotFound":
            error_message = "There were dependencies of the collada file not found in the file uploaded. Click 'Continue' to upload them."
            edit_link = reverse('content.views.upload', args=[task_id])
    elif res.state == "SUCCESS":
        if upload_rec['task_name'] == 'import_upload':
            success_message = "File was processed successfully. Click 'Continue' to add information to the file."
            edit_link = reverse('content.views.upload_import', args=[task_id])
        else:
            success_message = "File was imported successfully. Click 'Continue' to save."
            edit_link = reverse('content.views.upload_processing', args=['confirm', task_id])
    
    view_params = {'task_id': task_id,
                   'task_state': res.state,
                   'error_message': error_message,
                   'erase': erase,
                   'edit_link': edit_link,
                   'success_message': success_message}
    return render_to_response('content/processing.html', view_params, context_instance = RequestContext(request))

class UploadImport(forms.Form):
    def __init__(self, *args, **kwargs):
        super(UploadImport, self).__init__(*args, **kwargs)
        self.fields['title'] = forms.CharField(required=True, min_length=1, max_length=100, widget=forms.TextInput(attrs={
            'class': '{required:true, minlength:1, maxlength:100}'
        }))
        self.fields['path'] = forms.CharField(required=True, min_length=2, max_length=100, widget=forms.TextInput(attrs={
            'class': '{required:true, minlength:2, maxlength:100}'
        }))
        self.fields['description'] = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={
            'class': '{maxlength:1000}'
        }))
    def clean_path(self):
        path = self.cleaned_data['path']
        if not re.match("^[A-Za-z0-9_\.\-/]*$", path):
            raise forms.ValidationError("Valid characters are letters, numbers, and [._-/].")
        return path

def upload_import(request, task_id):
    if not request.user['is_authenticated']:
        return redirect('users.views.login')
    
    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseForbidden

    res = AsyncResult(task_id)
    if res.state != "SUCCESS":
        return HttpResponseForbidden

    filename = upload_rec['filename']
    filename_base = filename.split(".")[0]
    
    if request.method == 'POST':
        form = UploadImport(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            path = "/%s/%s" % (request.session['username'], form.cleaned_data['path'])
            description = form.cleaned_data['description']
            
            task = place_upload.delay(upload_rec['main_rowkey'], upload_rec['subfiles'],
                                      title, path, description, selected_dae=upload_rec['dae_choice'])
            
            save_upload_task(username=request.session['username'],
                             task_id=task.task_id,
                             row_key=upload_rec['main_rowkey'],
                             filename=upload_rec['filename'],
                             subfiles=upload_rec['subfiles'],
                             dae_choice=upload_rec['dae_choice'],
                             task_name="place_upload")
            
            try:
                remove_pending_upload(request.session['username'], task_id)
            except:
                return HttpResponseServerError("There was an error removing your old upload record.")
            
            return redirect('content.views.upload_processing', task_id=task.task_id)
            
    else:
        form = UploadImport(initial={'path':filename_base, 'title':filename_base.capitalize()})
    
    view_params = {'form': form,
                   'task_id': task_id,
                   'filename': filename}
    return render_to_response('content/import.html', view_params, context_instance = RequestContext(request))

def view(request, filename):
    file_metadata = get_file_metadata("/%s" % filename)
    view_params = {'metadata': file_metadata}
    view_params['basename'] = filename.split("/")[-2:][0]
    if file_metadata['type'] == 'image':
        html_page = 'content/view_image.html'
    else:
        html_page = 'content/view.html'
    return render_to_response(html_page, view_params, context_instance = RequestContext(request))

def download(request, hash, filename=None):
    rec = get_hash(hash)
    data = rec['data']
    mime = rec['mimetype']
    return HttpResponse(data, mimetype=mime)
