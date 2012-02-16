import posixpath
import collada
import tempfile
import hashlib
import numpy
import os
from StringIO import StringIO

from celery.task import task
from celery.execute import send_task

from meshtool.filters.panda_filters import pandacore
from meshtool.filters.panda_filters import pdae_utils
from meshtool.filters.simplify_filters import add_back_pm

from panda3d.core import GeomNode, NodePath, Mat4

from content.utils import get_file_metadata, save_file_data
from content.utils import add_metadata, get_hash
from content.utils import PathInfo

def getBam(mesh, filename):
    scene_members = pandacore.getSceneMembers(mesh)
    
    rotateNode = GeomNode("rotater")
    rotatePath = NodePath(rotateNode)
    matrix = numpy.identity(4)
    if mesh.assetInfo.upaxis == collada.asset.UP_AXIS.X_UP:
        r = collada.scene.RotateTransform(0,1,0,90)
        matrix = r.matrix
    elif mesh.assetInfo.upaxis == collada.asset.UP_AXIS.Y_UP:
        r = collada.scene.RotateTransform(1,0,0,90)
        matrix = r.matrix
    rotatePath.setMat(Mat4(*matrix.T.flatten().tolist()))
    
    for geom, renderstate, mat4 in scene_members:
        node = GeomNode("primitive")
        node.addGeom(geom)
        if renderstate is not None:
            node.setGeomState(0, renderstate)
        geomPath = rotatePath.attachNewNode(node)
        geomPath.setMat(mat4)

    rotatePath.flattenStrong()
    wrappedNode = pandacore.centerAndScale(rotatePath)
    
    model_name = filename.replace('/', '_')
    wrappedNode.setName(model_name)
    
    bam_temp = tempfile.mktemp(suffix = model_name + '.bam')
    wrappedNode.writeBamFile(bam_temp)
    
    bam_f = open(bam_temp, 'rb')
    bam_data = bam_f.read()
    bam_f.close()
    
    os.remove(bam_temp)
    
    return bam_data

@task
def generate_panda3d(filename, typeid):
    metadata = get_file_metadata(filename)
    hash = metadata['types'][typeid]['hash']
    subfiles = metadata['types'][typeid]['subfiles']
    progressive_stream = metadata['types'][typeid]['progressive_stream']
    progressive_data = get_hash(progressive_stream)['data'] if progressive_stream else None
    mipmaps = metadata['types'][typeid]['mipmaps']
    pathinfo = PathInfo(filename)
    dae_data = get_hash(hash)['data']

    mipmap_data = {}
    for mipmap_name, mipmap_info in mipmaps.iteritems():
        tar_hash = mipmap_info['hash']
        tar_data = get_hash(tar_hash)['data']
        
        min_range = None
        max_range = None
        min_size = 128
        for byte_range in mipmap_info['byte_ranges']:
            if byte_range['width'] <= min_size and byte_range['height'] <= min_size:
                min_range = (byte_range['offset'], byte_range['length'])
            max_range = (byte_range['offset'], byte_range['length'])

        mipmap_data[mipmap_name] = {}
        mipmap_data[mipmap_name]['base'] = tar_data[min_range[0]:min_range[0]+min_range[1]]
        mipmap_data[mipmap_name]['full'] = tar_data[max_range[0]:max_range[0]+max_range[1]]

    def base_loader(filename):
        return mipmap_data[filename]['base']
    def full_loader(filename):
        return mipmap_data[filename]['full']

    base_mesh = collada.Collada(StringIO(dae_data), aux_file_loader=base_loader)
    base_bam_data = getBam(base_mesh, 'base_' + filename)
    base_bam_hex_key = hashlib.sha256(base_bam_data).hexdigest()
    save_file_data(base_bam_hex_key, base_bam_data, "model/x-bam")

    full_mesh = collada.Collada(StringIO(dae_data), aux_file_loader=full_loader)
    if progressive_data is not None:
        full_mesh = add_back_pm.add_back_pm(full_mesh, StringIO(progressive_data), 100)
    full_bam_data = getBam(full_mesh, 'full_' + filename)
    full_bam_hex_key = hashlib.sha256(full_bam_data).hexdigest()
    save_file_data(full_bam_hex_key, full_bam_data, "model/x-bam")

    add_metadata(pathinfo.basepath, pathinfo.version, typeid, {'panda3d_base_bam': base_bam_hex_key,
                                                               'panda3d_full_bam': full_bam_hex_key})
