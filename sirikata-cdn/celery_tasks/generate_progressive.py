from celery.task import task
import collada
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
from content.utils import get_file_metadata, get_hash, save_file_data
from content.utils import add_metadata, get_new_version_from_path, save_file_name
import posixpath
import meshtool.filters
import hashlib
import zipfile
from content.utils import save_file_data, save_version_type
from celery.execute import send_task
from meshtool.filters.simplify_filters.sander_simplify import SanderSimplify

@task
def generate_progressive(filename, typeid):
    metadata = get_file_metadata(filename)
    hash = metadata['types'][typeid]['hash']
    subfiles = metadata['types'][typeid]['subfiles']
    path, version = posixpath.split(filename)

    dae_data = get_hash(hash)['data']

    subfile_map = {}
    for subfile in subfiles:
        img_meta = get_file_metadata(subfile)
        img_hash = img_meta['hash']
        img_data = get_hash(img_hash)['data']
        base_name = posixpath.basename(posixpath.split(subfile)[0])
        subfile_map[base_name] = img_data

    def customImageLoader(filename):
        return subfile_map[posixpath.basename(filename)]

    mesh = collada.Collada(StringIO(dae_data), aux_file_loader=customImageLoader)

    strip_lines = meshtool.filters.factory.getInstance('strip_lines')
    mesh = strip_lines.apply(mesh)
    med_opts = meshtool.filters.factory.getInstance('medium_optimizations')
    mesh = med_opts.apply(mesh)

    progressive_stream = StringIO()
    sander_simplify = SanderSimplify(mesh, progressive_stream)
    mesh = sander_simplify.simplify()
    
    if sander_simplify.base_tri_count != sander_simplify.orig_tri_count:
        progressive_stream = progressive_stream.getvalue()
        progressive_hex_key = hashlib.sha256(progressive_stream).hexdigest()
        save_file_data(progressive_hex_key, progressive_stream, "model/vnd.pdae")
        progressive_stream_num_triangles = sander_simplify.orig_tri_count - sander_simplify.base_tri_count
    else:
        progressive_hex_key = None
        progressive_stream_num_triangles = 0

    #Make sure image paths are just the base name
    current_prefix = "progressive"
    subfile_names = []
    subfile_map = {}
    for img in mesh.images:
        base_name = posixpath.basename(img.path)
        subfile_map[base_name] = img.data

        img_hex_key = hashlib.sha256(subfile_map[base_name]).hexdigest()
        save_file_data(img_hex_key, subfile_map[base_name], "image/%s" % img.pilimage.format.lower())
        img_path = "%s/%s/%s" % (path, current_prefix, base_name)
        img_len = len(subfile_map[base_name])
        img_version_num = get_new_version_from_path(img_path, file_type="image")
        save_file_name(img_path, img_version_num, img_hex_key, img_len)
        subfile_names.append("%s/%s" % (img_path, img_version_num))

    str_buffer = StringIO()
    mesh.write(str_buffer)
    orig_save_data = str_buffer.getvalue()
    orig_hex_key = hashlib.sha256(orig_save_data).hexdigest()

    save_file_data(orig_hex_key, orig_save_data, "application/xml")

    zip_buffer = StringIO()
    combined_zip = zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED)
    combined_zip.writestr(posixpath.basename(path), orig_save_data)
    for img_name, img_data in subfile_map.iteritems():
        combined_zip.writestr(img_name, img_data)
    combined_zip.close()

    zip_save_data = zip_buffer.getvalue()
    zip_hex_key = hashlib.sha256(zip_save_data).hexdigest()
    save_file_data(zip_hex_key, zip_save_data, "application/zip")

    save_version_type(path, version, orig_hex_key, len(orig_save_data),
                      subfile_names, zip_hex_key, "progressive")

    add_metadata(path, version, "progressive", { 'progressive_stream': progressive_hex_key,
                                                 'progressive_stream_num_triangles': progressive_stream_num_triangles  })

    send_task("celery_tasks.generate_screenshot.generate_screenshot", args=[filename, "progressive"])
    send_task("celery_tasks.generate_metadata.generate_metadata", args=[filename, "progressive"])
