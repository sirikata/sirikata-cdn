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

from users.middleware import save_upload_task, get_pending_upload, \
                             remove_pending_upload, save_file_upload

from content.utils import get_file_metadata, get_hash, get_content_by_date
from content.utils import add_base_metadata, delete_file_metadata
from content.utils import get_versions

from celery_tasks.import_upload import import_upload, place_upload
from celery_tasks.import_upload import ColladaError, DatabaseError, NoDaeFound

from celery.execute import send_task
from celery.result import AsyncResult

def json_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    #elif isinstance(obj, ...):
    #    return ...
    else:
        raise TypeError, 'Object of type %s with value of %s is not JSON serializable' % (type(Obj), repr(Obj))

def browse(request, start=""):
    content_items, next_start, prev_start = get_content_by_date(start=start)
    view_params = {'content_items': content_items, 'next_start': next_start,
                   'prev_start': prev_start }
    return render_to_response('content/browse.html', view_params, context_instance = RequestContext(request))

def browse_json(request, start=""):
    content_items, next_start = get_content_by_date(start=start)
    view_params = {'content_items': content_items, 'next_start': next_start}
    response = HttpResponse(simplejson.dumps(view_params, default=json_handler), mimetype='application/json')
    response['Access-Control-Allow-Origin'] = '*'
    return response

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
    if not request.user['is_authenticated']:
        return redirect('users.views.login')

    try:
        upload_rec = get_pending_upload(request.session['username'], task_id)
    except:
        return HttpResponseForbidden()

    res = AsyncResult(task_id)

    xhr = request.GET.has_key('xhr')
    if xhr:
        json_result = {'state':res.state}
        return HttpResponse(simplejson.dumps(json_result, default=json_handler), mimetype='application/json')

    if action == 'confirm':
        if upload_rec['task_name'] == 'import_upload':
            try:
                remove_pending_upload(request.session['username'], task_id)
            except:
                return HttpResponseServerError("There was an error removing your upload record.")
            messages.info(request, 'Upload removed')
            return redirect('users.views.uploads')
        elif res.state == "FAILURE":
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
        return HttpResponseForbidden()

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

class EditFile(forms.Form):
    def __init__(self, *args, **kwargs):
        super(EditFile, self).__init__(*args, **kwargs)
        self.fields['title'] = forms.CharField(required=True, min_length=1, max_length=100, widget=forms.TextInput(attrs={
            'class': '{required:true, minlength:1, maxlength:100}'
        }))
        self.fields['description'] = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={
            'class': '{maxlength:1000}'
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

            try:
                updated_info = {'title': title, 'description': description}
                add_base_metadata(basepath, version, updated_info)
            except:
                return HttpResponseServerError("There was an error editing your file.")

            return redirect('content.views.view', filename)
    else:
        form = EditFile(initial={'title':file_metadata['title'], 'description':file_metadata['description']})

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
    view_params['all_versions'] = versions
    view_params['latest_version'] = latest_version
    file_username = split[0]

    view_params['can_change'] = False
    if file_username == request.user.get('username'):
        view_params['can_change'] = True

    if file_metadata['type'] == 'image':
        html_page = 'content/view_image.html'
    else:
        html_page = 'content/view.html'
    return render_to_response(html_page, view_params, context_instance = RequestContext(request))

def view_json(request, filename):
    try: file_metadata = get_file_metadata("/%s" % filename)
    except NotFoundError: return HttpResponseNotFound()

    view_params = {'metadata': file_metadata}

    split = filename.split("/")
    view_params['version'] = split[-1]
    view_params['basename'] = split[-2]
    view_params['basepath'] = "/".join(split[:-1])
    view_params['fullpath'] = filename
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
                        start = int(parts[0])
                        end = int(parts[1])
                        rangeheader = "bytes %d-%d/%d" % (start, end, len(data))
                        end += 1
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
    return response

def dns(request, filename):
    if request.method != 'HEAD':
        return HttpResponseBadRequest()

    parts = filename.split("/")
    if len(parts) < 4:
        return HttpResponseBadRequest()
    base_path = "/".join(parts[:-3])
    type_id = parts[-3]
    version_num = parts[-2]
    requested_file = parts[-1]

    try: file_metadata = get_file_metadata("/%s/%s" % (base_path, version_num))
    except NotFoundError: return HttpResponseNotFound()
    except: return HttpResponseServerError()

    if type_id not in file_metadata['types']:
        return HttpResponseNotFound()

    if requested_file == posixpath.basename(base_path):
        hash = file_metadata['types'][type_id]['hash']
        file_size = file_metadata['types'][type_id]['size']
    else:
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

    response = HttpResponse()
    response['Hash'] = hash
    response['File-Size'] = file_size
    return response
