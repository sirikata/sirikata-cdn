from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django import forms
from django.http import HttpResponseServerError, HttpResponseForbidden
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils import simplejson
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
import re
import posixpath
from cassandra_storage.cassandra_util import NotFoundError

from oauth_server import oauth_server

from users.middleware import save_upload_task, get_pending_upload, \
                             remove_pending_upload, save_file_upload, \
                             login_required

from content.utils import get_file_metadata, get_hash, get_content_by_date
from content.utils import add_base_metadata, delete_file_metadata
from content.utils import get_versions, copy_file, update_ttl
from content.utils import user_search, get_content_by_name
from content.utils import PathInfo

from celery_tasks.import_upload import import_upload, place_upload
from celery_tasks.import_upload import ColladaError, DatabaseError, NoDaeFound

from celery.execute import send_task
from celery.result import AsyncResult

MIN_TTL = 60
MAX_TTL = 86400
INITIAL_TTL = 3600

def json_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    #elif isinstance(obj, ...):
    #    return ...
    else:
        raise TypeError, 'Object of type %s with value of %s is not JSON serializable' % (type(Obj), repr(Obj))

def browse(request):
    start = request.GET.get('start', '')
    view = request.GET.get('view', 'icon')
    try: count = int(request.GET.get('count', 25))
    except ValueError: count = 25
    try: reverse = bool(int(request.GET.get('reverse', True)))
    except ValueError: reverse = True

    (content_items, older_start, newer_start) = get_content_by_date(start=start, limit=count, reverse=reverse)
    view_params = {
        'content_items': content_items,
        'older_start': older_start,
        'newer_start': newer_start,
        'get_params': request.GET,
        'view': view
    }
    return render_to_response('content/browse.html', view_params, context_instance = RequestContext(request))

@decorator_from_middleware(GZipMiddleware)
def browse_json(request, start=""):
    (content_items, older_start, newer_start) = get_content_by_date(start=start)
    view_params = {'content_items': content_items, 'next_start': older_start, 'previous_start': newer_start}
    response = HttpResponse(simplejson.dumps(view_params, default=json_handler, indent=4), mimetype='application/json')
    response['Access-Control-Allow-Origin'] = '*'
    return response

class UploadChoiceForm(forms.Form):
    def __init__(self, task_id, choices, *args, **kwargs):
        super(UploadChoiceForm, self).__init__(*args, **kwargs)
        self.fields['file'] = forms.ChoiceField(choices=[(str(i),c) for i,c in enumerate(choices)],
                                                required=True, widget=forms.Select(attrs={
            'class': '{required:true}'
        }))

@login_required
def upload_choice(request, task_id):

    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseForbidden()
    res = AsyncResult(task_id)
    if res.state == "FAILURE" and type(res.result).__name__ == "TooManyDaeFound":
        names = res.result.names
    else:
        return HttpResponseForbidden()

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
        self.file_names = file_names
        for f in file_names:
            self.fields[f] = forms.FileField(label=f, required=True, widget=forms.FileInput(attrs={
                'class': '{required:true}'
            }))

@login_required
def upload(request, task_id=None):

    if task_id:
        try:
            upload_rec = get_pending_upload(request.session['username'], task_id)
        except:
            return HttpResponseForbidden()
        orig_name = upload_rec['filename']
        subfiles_uploaded = upload_rec['subfiles']
        existing_files = subfiles_uploaded.keys()
        existing_files.append(orig_name)
        res = AsyncResult(task_id)
        if res.state == "FAILURE" and type(res.result).__name__ == "SubFilesNotFound":
            names = res.result.names
        else:
            return HttpResponseForbidden()

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
    username = request.GET.get('username')
    user_authed = False
    if request.user['is_authenticated']:
        user_authed = True
        if username is None:
            username = request.session['username']

    try:
        upload_rec = get_pending_upload(username, task_id)
    except:
        return HttpResponseForbidden()

    res = AsyncResult(task_id)

    xhr = request.GET.has_key('xhr')
    if xhr:
        json_result = {'state':res.state}
        if res.state == 'SUCCESS':
            json_result['path'] = res.result
        return HttpResponse(simplejson.dumps(json_result, default=json_handler), mimetype='application/json')

    api = request.GET.has_key('api')
    if api:
        json_result = {'state':res.state}
        if res.state == 'FAILURE':
            try:
                remove_pending_upload(username, task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
        elif res.state == 'SUCCESS':
            path = res.result
            json_result['path'] = path
            if not upload_rec['ephemeral']:
                try:
                    save_file_upload(username, path)
                except:
                    return HttpResponseServerError("There was an error saving your upload.")
            try:
                remove_pending_upload(username, task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
        return HttpResponse(simplejson.dumps(json_result, default=json_handler), mimetype='application/json')

    if user_authed and username == request.session['username'] and action == 'confirm':
        if upload_rec['task_name'] == 'import_upload':
            try:
                remove_pending_upload(username, task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
            messages.info(request, 'Upload removed')
            return redirect('users.views.uploads')
        elif res.state == "FAILURE":
            try:
                remove_pending_upload(username, task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
            messages.info(request, 'Upload removed')
            return redirect('users.views.uploads')
        else:
            path = res.result
            try:
                save_file_upload(username, path)
            except:
                return HttpResponseServerError("There was an error saving your upload.")
            try:
                remove_pending_upload(username, task_id)
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
        else:
            error_message = "An unknown error has occurred."
            erase = True
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
        self.fields['labels'] = forms.CharField(required=False, max_length=1000, widget=forms.TextInput(attrs={
            'class': '{maxlength:1000}'
        }))
    def clean_path(self):
        path = self.cleaned_data['path']
        if not re.match("^[A-Za-z0-9_\.\-/]*$", path):
            raise forms.ValidationError("Valid characters are letters, numbers, and [._-/].")
        return path

@login_required
def upload_import(request, task_id):

    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseNotFound()

    res = AsyncResult(task_id)
    if res.state != "SUCCESS":
        return HttpResponseForbidden()

    filename = upload_rec['filename']
    filename_base = filename.split(".")[0]

    if request.method == 'POST':
        form = UploadImport(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            path = "/%s/%s" % (request.session['username'], form.cleaned_data['path'])
            description = form.cleaned_data['description']
            labels = form.cleaned_data['labels'].split(',')
            labels = [label.strip() for label in labels]

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
        if res.result is None:
            default_filename = filename
        else:
            default_filename = res.result
        form = UploadImport(initial={'path':default_filename, 'title':filename_base.capitalize()})

    view_params = {'form': form,
                   'task_id': task_id,
                   'filename': filename}
    return render_to_response('content/import.html', view_params, context_instance = RequestContext(request))

class APIUpload(UploadImport, UploadForm):
    def __init__(self, *args, **kwargs):
        super(APIUpload, self).__init__(*args, **kwargs)
        self.fields['main_filename'] = forms.CharField(required=True, min_length=1, max_length=100)
        self.fields['subfiles'] = forms.CharField(required=False, min_length=1, max_length=10000, initial=None)
        self.fields['ephemeral'] = forms.BooleanField(required=False, initial=False)
        # minimum 10 minutes, maximum 24 hours, default 1 hour
        self.fields['ttl_time'] = forms.IntegerField(required=False, min_value=MIN_TTL, max_value=MAX_TTL, initial=INITIAL_TTL)
        
    def clean_main_filename(self):
        main_filename = self.cleaned_data['main_filename']
        if main_filename not in self.file_names:
            raise forms.ValidationError("Given main_filename not in uploaded files.")
        return main_filename
    
    def get_subfiles(self):
        return simplejson.loads(self.cleaned_data['subfiles']) if len(self.cleaned_data['subfiles']) > 0 else {}
    
    def clean_subfiles(self):
        try:
            subfiles = self.get_subfiles()
            if len(subfiles) == 0:
                return ''
        except simplejson.JSONDecodeError:
            raise forms.ValidationError("Invalid subfiles json")

        if not isinstance(subfiles, dict) or not \
                all(isinstance(k, basestring) and isinstance(v, basestring)
                    for k,v in subfiles.iteritems()):
            raise forms.ValidationError("Invalid subfiles dictionary")
        
        subfiles = dict((posixpath.normpath(k), v) for k,v in subfiles.iteritems())
        
        return simplejson.dumps(subfiles)

    def clean(self):
        cleaned_data = super(APIUpload, self).clean()
        
        subfiles = cleaned_data.get('subfiles')
        ephemeral = cleaned_data.get('ephemeral')
        ttl_time = cleaned_data.get('ttl_time')
        
        if not ephemeral and ttl_time:
            raise forms.ValidationError("TTL time is only valid when uploading ephemeral files")
        if not ephemeral and subfiles:
            raise forms.ValidationError("Subfiles parameter is only valid when uploading ephemeral files")
        
        if ephemeral and len(self.file_names) > 1:
            raise forms.ValidationError("Only one file can be uploaded when uploading an ephemeral file")
        
        return self.cleaned_data

@csrf_exempt
def api_upload(request):
    result = {}
    if request.method != 'POST':
        result['success'] = False
        result['error'] = 'Invalid request'
    else:
        oauth_request = oauth_server.request_from_django(request)
        verified = oauth_server.verify_access_request(oauth_request) if oauth_request else False
        if not verified:
            result['success'] = False
            result['error'] = 'OAuth Authentication Error'
        else:
            params = ['path', 'main_filename', 'title',
                      'description', 'subfiles', 'ephemeral',
                      'ttl_time', 'labels']
            
            upload_data = dict((param, oauth_request.get(param))
                               for param in params)

            form = APIUpload(data=upload_data,
                             files=request.FILES,
                             file_names=request.FILES.keys())
            if not form.is_valid():
                result['success'] = False
                # Only log these errors if we haven't encountered some other error first.
                if 'error' not in result:
                    errors = []
                    for field in form:
                        if field.errors:
                            errors.append("%s:%s" % (field.name, field.errors))
                    result['error'] = "Invalid form fields.\n" + form.errors.as_text()
                
            else:
                title = form.cleaned_data['title']
                username = oauth_request.get_parameter('username')
                path = "/%s/%s" % (username, form.cleaned_data['path'])
                description = form.cleaned_data['description']
                labels = form.cleaned_data['labels'].split(',')
                labels = [label.strip() for label in labels]
                main_filename = form.cleaned_data['main_filename']
                ephemeral = form.cleaned_data['ephemeral']
                ttl_time = form.cleaned_data['ttl_time']
                ephemeral_subfiles = form.get_subfiles()
    
                main_rowkey = request.FILES[main_filename].row_key
                subfiles = {}
                for fname, fobj in request.FILES.iteritems():
                    if fname != main_filename:
                        subfiles[fname] = fobj.row_key
                dae_choice = ""
                filename = main_filename

                if ephemeral:
                    task = place_upload.delay(main_rowkey, ephemeral_subfiles, title, path,
                                              description, create_index=False, ephemeral_ttl=ttl_time)
                else:
                    task = place_upload.delay(main_rowkey, subfiles, title, path,
                                              description, create_index=True)
    
                save_upload_task(username=username,
                                 task_id=task.task_id,
                                 row_key=main_rowkey,
                                 filename=filename,
                                 subfiles=subfiles,
                                 dae_choice="",
                                 task_name="place_upload",
                                 ephemeral=ephemeral)
                
                result['success'] = True
                result['task_id'] = task.task_id
    
    response = HttpResponse(simplejson.dumps(result, default=json_handler, indent=4), mimetype='application/json')
    return response

class EditFile(forms.Form):
    def __init__(self, *args, **kwargs):
        super(EditFile, self).__init__(*args, **kwargs)
        self.fields['title'] = forms.CharField(required=True, min_length=1, max_length=100, widget=forms.TextInput(attrs={
            'class': '{required:true, minlength:1, maxlength:100}'
        }))
        self.fields['description'] = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={
            'class': '{maxlength:1000}'
        }))
        self.fields['labels'] = forms.CharField(required=False, max_length=1000, widget=forms.TextInput(attrs={
            'class': '{maxlength:1000}', 'style': 'width: 400px'
        }))
def edit_file(request, filename):
    try: file_metadata = get_file_metadata("/%s" % filename)
    except NotFoundError: return HttpResponseNotFound()

    split = filename.split("/")
    file_username = split[0]
    basepath = "/" + "/".join(split[:-1])
    version = split[-1:][0]

    if file_username != request.user.get('username'):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = EditFile(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            description = form.cleaned_data['description']
            labels = form.cleaned_data['labels'].split(',')
            labels = [label.strip() for label in labels]

            try:
                updated_info = {
                    'title': title,
                    'description': description,
                    'labels': labels,
                }
                add_base_metadata(basepath, version, updated_info)
            except:
                return HttpResponseServerError("There was an error editing your file.")

            return redirect('content.views.view', filename)
    else:
        form = EditFile(initial={
            'title': file_metadata['title'],
            'description' : file_metadata['description'],
            'labels': ', '.join(file_metadata.get('labels', []))
        })

    view_params = {'form': form,
                   'filename': filename}
    return render_to_response('content/edit.html', view_params, context_instance = RequestContext(request))

def delete_file(request, filename):
    try: file_metadata = get_file_metadata("/%s" % filename)
    except NotFoundError: return HttpResponseNotFound()

    split = filename.split("/")
    file_username = split[0]
    basepath = "/" + "/".join(split[:-1])
    version = split[-1:][0]

    if file_username != request.user.get('username'):
        return HttpResponseForbidden()

    delete_file_metadata(basepath, version)

    return redirect('users.views.uploads')

class CloneFile(forms.Form):
    def __init__(self, *args, **kwargs):
        super(CloneFile, self).__init__(*args, **kwargs)
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

@login_required
def clone_file(request, filename):
    
    try: file_metadata = get_file_metadata("/%s" % filename)
    except NotFoundError: return HttpResponseNotFound()
    
    split = filename.split("/")
    file_username = split[0]
    basepath = "/" + "/".join(split[:-1])
    postpath = "/".join(split[1:-1])
    version = split[-1:][0]
    
    if request.method == 'POST':
        form = CloneFile(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            description = form.cleaned_data['description']
            path = "/%s/%s" % (request.session['username'], form.cleaned_data['path'])
            updated_info = {'title': title, 'description': description}
            try:
                new_filename = copy_file(basepath, version, path, updated_info)
            except:
                return HttpResponseServerError("There was an error cloning your file.")
            return redirect('content.views.view', new_filename[1:])
    else:
        form = CloneFile(initial={'path':postpath, 'title':file_metadata['title'], 'description':file_metadata['description']})
    
    view_params = {}
    view_params['clone_path'] = filename
    view_params['form'] = form
    return render_to_response('content/clone.html', view_params, context_instance = RequestContext(request))

def view(request, filename):    
    split = filename.split("/")
    try:
        version = str(int(split[-1]))
    except ValueError:
        version = None

    if version is None:
        basename = split[-1]
        basepath = filename
    else:
        basename = split[-2]
        basepath = '/'.join(split[:-1])

    versions = get_versions('/' + basepath)
    if versions is None:
        return HttpResponseNotFound()

    latest_version = str(max(map(int, versions)))
    if version is None:
        version = latest_version

    try: file_metadata = get_file_metadata("/%s/%s" % (basepath, version))
    except NotFoundError: return HttpResponseNotFound()

    view_params = {'metadata': file_metadata}

    view_params['version'] = version
    view_params['basename'] = basename
    view_params['basepath'] = basepath
    view_params['fullpath'] = filename
    view_params['all_versions'] = map(str, sorted(map(int, versions)))
    view_params['latest_version'] = latest_version
    file_username = split[0]

    view_params['can_change'] = False
    if file_username == request.user.get('username'):
        view_params['can_change'] = True
        
    view_params['can_clone'] = False
    if request.user['is_authenticated'] and file_username != request.user.get('username'):
        view_params['can_clone'] = True
    
    if file_metadata['type'] == 'image':
        html_page = 'content/view_image.html'
    else:
        html_page = 'content/view.html'
    return render_to_response(html_page, view_params, context_instance = RequestContext(request))

@decorator_from_middleware(GZipMiddleware)
def view_json(request, filename):
    try: file_metadata = get_file_metadata("/%s" % filename)
    except NotFoundError: return HttpResponseNotFound()

    view_params = {'metadata': file_metadata}

    split = filename.split("/")
    view_params['version'] = split[-1]
    view_params['basename'] = split[-2]
    view_params['basepath'] = "/".join(split[:-1])
    view_params['fullpath'] = filename
    response = HttpResponse(simplejson.dumps(view_params, default=json_handler, indent=4), mimetype='application/json')
    response['Access-Control-Allow-Origin'] = '*'
    return response

def ephemeral_keepalive(request, filename):
    oauth_request = oauth_server.request_from_django(request)
    verified = oauth_server.verify_access_request(oauth_request) if oauth_request else False
    if not verified:
        return HttpResponseBadRequest()
    
    # make sure file being updated matches the username in the oauth request 
    filename = '/' + filename
    username = request.GET.get('username')
    if not filename.startswith('/' + username):
        return HttpResponseBadRequest()
    
    ttl_time = int(request.GET.get('ttl', INITIAL_TTL))
    if ttl_time < MIN_TTL or ttl_time > MAX_TTL:
        return HttpResponseBadRequest()
    
    update_ttl(filename, ttl_time)
    
    return HttpResponse("")

def search(request):
    query = request.GET.get('q', '')
    results = user_search(query)
    names = [result['id'] for result in results]
    results = get_content_by_name(names)
    view_params = {
        'query': query,
        'results': results
    }
    return render_to_response('content/search.html', view_params, context_instance = RequestContext(request))

def search_json(request):
    query = request.REQUEST.get('q', '')
    results = user_search(query)
    view_params = {'results': results}
    response = HttpResponse(simplejson.dumps(view_params, default=json_handler), mimetype='application/json')
    response['Access-Control-Allow-Origin'] = '*'
    return response

@decorator_from_middleware(GZipMiddleware)
def download(request, hash, filename=None):
    try: rec = get_hash(hash)
    except NotFoundError: return HttpResponseNotFound()
    except: return HttpResponseServerError()
    data = rec['data']
    mime = rec['mimetype']
    if request.method == 'HEAD':
        response = HttpResponse(mimetype=mime)
    else:
        rangedresponse = False
        if 'HTTP_RANGE' in request.META:
            range = request.META['HTTP_RANGE']
            parts = range.split('=')
            if len(parts) == 2:
                parts = parts[1].split('-')
                if len(parts) == 2:
                    try:
                        start = max(0, int(parts[0]))
                        end = int(parts[1])
                        rangeheader = "bytes %d-%d/%d" % (start, end, len(data))
                        end += 1
                        end = min(len(data), end)
                        if start >= 0 and end > 0 and \
                            start < end and end <= len(data):
                            rangedresponse = True
                            data = data[start:end]
                    except ValueError: pass
        response = HttpResponse(data, mimetype=mime)
        if rangedresponse:
            response['Content-Range'] = rangeheader
            response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(len(data))
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Range'
    return response

def dns(request, filename):
    send_body = False
    if request.method != 'HEAD' and request.method != 'GET':
        return HttpResponseBadRequest()

    #check if filename exists as-is, otherwise try meerkat URI
    try:
        file_metadata = get_file_metadata("/" + filename)
        pathinfo = PathInfo(filename)
        requested_file = pathinfo.basename
        version_num = pathinfo.version
        base_path = pathinfo.basepath
        hash = file_metadata['hash']
        file_size = file_metadata['size']
        is_mesh = False
        meerkat = False
    except NotFoundError:
        meerkat = True

    if meerkat:
        parts = posixpath.normpath(filename).split("/")
        if len(parts) < 3:
            return HttpResponseBadRequest()
        
        requested_file = parts[-1]
    
        try: version_num = str(int(parts[-2]))
        except ValueError: version_num = None
        
        if version_num is None:
            base_path = "/".join(parts[:-2])
            type_id = parts[-2]
            versions = get_versions('/' + base_path)
            version_num = str(max(map(int, versions)))
        else:
            base_path = "/".join(parts[:-3])
            type_id = parts[-3]
    
        try: file_metadata = get_file_metadata("/%s/%s" % (base_path, version_num))
        except NotFoundError: return HttpResponseNotFound()
        except: return HttpResponseServerError()

        if type_id not in file_metadata['types']:
            return HttpResponseNotFound()

        if requested_file == posixpath.basename(base_path):
            is_mesh = True
            hash = file_metadata['types'][type_id]['hash']
            file_size = file_metadata['types'][type_id]['size']
        else:
            is_mesh = False
            subfile_map = {}
            for subfile in file_metadata['types'][type_id]['subfiles']:
                (subfile_base, vers) = posixpath.split(subfile)
                subfile_basename = posixpath.basename(subfile_base)
                subfile_map[subfile_basename] = subfile
    
            if requested_file not in subfile_map:
                return HttpResponseNotFound()
    
            subfile_metadata = get_file_metadata(subfile_map[requested_file])
            hash = subfile_metadata['hash']
            file_size = subfile_metadata['size']
    
    if request.method == 'GET':
        body = {'Hash': hash, 'File-Size': file_size}
        bodydata = simplejson.dumps(body)
        response = HttpResponse(bodydata, mimetype='application/json')
    else:
        response = HttpResponse()
        
    if is_mesh and 'progressive_stream' in file_metadata['types'][type_id] and file_metadata['types'][type_id]['progressive_stream'] is not None:
        response['Progresive-Stream'] = file_metadata['types'][type_id]['progressive_stream']
    if is_mesh and 'progressive_stream_num_triangles' in file_metadata['types'][type_id]:
        response['Progresive-Stream-Num-Triangles'] = file_metadata['types'][type_id]['progressive_stream_num_triangles']

    if is_mesh and 'metadata' in file_metadata['types'][type_id]:
        extra_metadata = file_metadata['types'][type_id]['metadata']
        if 'num_triangles' in extra_metadata:
            response['Num-Triangles'] = extra_metadata['num_triangles']
        if 'zernike' in extra_metadata:
            response['Zernike']  = ','.join(map(str, extra_metadata['zernike']))

    if is_mesh and 'subfiles' in file_metadata['types'][type_id]:
        subfiles = file_metadata['types'][type_id]['subfiles']
        response['Subfiles'] = len(subfiles)
        for subfile_number, subfile_path in enumerate(subfiles):
            pathinfo = PathInfo(subfile_path)
            response['Subfile-%d-Name' % subfile_number] = pathinfo.basename
            response['Subfile-%d-Path' % subfile_number] = pathinfo.normpath

    if is_mesh and 'mipmaps' in file_metadata['types'][type_id]:
        mipmaps = file_metadata['types'][type_id]['mipmaps']
        response['Mipmaps'] = len(mipmaps)
        for mipmap_number, (mipmap_name, mipmap_data) in enumerate(mipmaps.iteritems()):
            response['Mipmap-%d-Name' % mipmap_number] = mipmap_name
            response['Mipmap-%d-Hash' % mipmap_number] = mipmap_data['hash']
            for mipmap_level_number, mipmap_level in enumerate(mipmap_data['byte_ranges']):
                response['Mipmap-%d-Level-%d' % (mipmap_number,mipmap_level_number)] = '%s,%s,%s,%s' % (mipmap_level['offset'], mipmap_level['length'], mipmap_level['width'], mipmap_level['height'])

    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Expose-Headers'] = 'Hash, File-Size'
    response['Hash'] = hash
    response['File-Size'] = file_size

    return response

def compare_progressive(request):
    (content_items, older_start, newer_start) = get_content_by_date(start="", limit=5000)
    view_params = {
        'content_items': content_items,
    }
    return render_to_response('content/compare_progressive.html', view_params, context_instance = RequestContext(request))
