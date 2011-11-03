from celery.task import task
import os
import sys
import collada
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
from content.utils import get_file_metadata, get_hash, save_file_data, add_metadata
from meshtool.filters.print_filters.print_json import getJSON
import meshtool.filters
import json
import os.path
import posixpath
import tempfile
import subprocess

@task
def generate_metadata(filename, typeid):
    metadata = get_file_metadata(filename)
    hash = metadata['types'][typeid]['hash']
    subfiles = metadata['types'][typeid]['subfiles']
    
    dae_data = get_hash(hash)['data']

    subfile_map = {}
    for subfile in subfiles:
        img_meta = get_file_metadata(subfile)
        img_hash = img_meta['hash']
        img_data = get_hash(img_hash)['data']
        base_name = os.path.basename(os.path.split(subfile)[0])
        subfile_map[base_name] = img_data
    
    def customImageLoader(filename):
        return subfile_map[posixpath.basename(filename)]
    
    mesh = collada.Collada(StringIO(dae_data), aux_file_loader=customImageLoader)
    json_data = json.loads(getJSON(mesh))

    metadata_info = {}
    metadata_info['num_triangles'] = json_data['num_triangles']
    metadata_info['num_materials'] = len(json_data['materials'])
    metadata_info['num_images'] = len(json_data['images'])
    metadata_info['texture_ram_usage'] = json_data['texture_ram']
    metadata_info['num_draw_calls'] = json_data['num_draw_with_batching']
    metadata_info['num_vertices'] = json_data['num_vertices']

    triangulate = meshtool.filters.factory.getInstance('triangulate')
    mesh = triangulate.apply(mesh)
    save_ply = meshtool.filters.factory.getInstance('save_ply')
    ply_temp_file = tempfile.mktemp(suffix='.ply', prefix='meshtool-genmetadata-zernike')
    save_ply.apply(mesh, ply_temp_file)
    
    zernike_calc = os.path.join(os.path.dirname(__file__), 'zernike_calculator')
    zernike_output = subprocess.check_output([zernike_calc, ply_temp_file])
    zernike_nums = zernike_output.split(',')
    zernike_nums = map(float, zernike_nums)
    metadata_info['zernike'] = zernike_nums
    os.remove(ply_temp_file)

    split = filename.split("/")
    version = split[-1:][0]
    file_key = "/".join(split[:-1])
    add_metadata(file_key, version, typeid, { 'metadata': metadata_info })
