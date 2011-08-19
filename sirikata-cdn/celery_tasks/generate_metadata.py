from celery.task import task
import os
import sys
import collada
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
from content.utils import get_file_metadata, get_hash, save_file_data, add_metadata
from meshtool.filters.print_filters.print_json import getJSON
import json
import os.path
import posixpath

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

    split = filename.split("/")
    version = split[-1:][0]
    file_key = "/".join(split[:-1])
    add_metadata(file_key, version, typeid, { 'metadata': metadata_info })
