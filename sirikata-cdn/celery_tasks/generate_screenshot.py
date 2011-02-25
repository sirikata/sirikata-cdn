import collada
from celery.task import task
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
from content.utils import get_file_metadata, get_hash, save_file_data, add_metadata
import os.path
import Image
import hashlib

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import GeomVertexFormat
from panda3d.core import GeomVertexData
from panda3d.core import GeomVertexWriter
from panda3d.core import GeomTriangles
from panda3d.core import Geom
from panda3d.core import GeomNode
from panda3d.core import PNMImage
from panda3d.core import Texture
from panda3d.core import StringStream
from panda3d.core import Filename
from panda3d.core import RenderState
from panda3d.core import TextureAttrib
from panda3d.core import MaterialAttrib
from panda3d.core import Material, SparseArray
from panda3d.core import VBase4, Vec4, Point3, Mat4, Point2
from panda3d.core import AmbientLight, DirectionalLight
from panda3d.core import Character, PartGroup, CharacterJoint
from panda3d.core import TransformBlend, TransformBlendTable, JointVertexTransform
from panda3d.core import GeomVertexAnimationSpec, GeomVertexArrayFormat, InternalName
from panda3d.core import AnimBundle, AnimGroup, AnimChannelMatrixXfmTable
from panda3d.core import PTAFloat, CPTAFloat, AnimBundleNode, NodePath
from direct.actor.Actor import Actor
from panda3d.core import loadPrcFileData

def getNodeFromController(controller, controlled_prim, subfile_map):
        if type(controlled_prim) is collada.controller.BoundSkinPrimitive:
            ch = Character('simplechar')
            bundle = ch.getBundle(0)
            skeleton = PartGroup(bundle, '<skeleton>')

            character_joints = {}
            for (name, joint_matrix) in controller.joint_matrices.iteritems():
                joint_matrix.shape = (-1)
                character_joints[name] = CharacterJoint(ch, bundle, skeleton, name, Mat4(*joint_matrix)) 
            
            tbtable = TransformBlendTable()
            
            for influence in controller.index:
                blend = TransformBlend()
                for (joint_index, weight_index) in influence:
                    char_joint = character_joints[controller.getJoint(joint_index)]
                    weight = controller.getWeight(weight_index)[0]
                    blend.addTransform(JointVertexTransform(char_joint), weight)
                tbtable.addBlend(blend)
                
            array = GeomVertexArrayFormat()
            array.addColumn(InternalName.make('vertex'), 3, Geom.NTFloat32, Geom.CPoint)
            array.addColumn(InternalName.make('normal'), 3, Geom.NTFloat32, Geom.CPoint)
            array.addColumn(InternalName.make('texcoord'), 2, Geom.NTFloat32, Geom.CTexcoord)
            blendarr = GeomVertexArrayFormat()
            blendarr.addColumn(InternalName.make('transform_blend'), 1, Geom.NTUint16, Geom.CIndex)
            
            format = GeomVertexFormat()
            format.addArray(array)
            format.addArray(blendarr)
            aspec = GeomVertexAnimationSpec()
            aspec.setPanda()
            format.setAnimation(aspec)
            format = GeomVertexFormat.registerFormat(format)
            
            dataname = controller.id + '-' + controlled_prim.primitive.material.id
            vdata = GeomVertexData(dataname, format, Geom.UHStatic)
            vertex = GeomVertexWriter(vdata, 'vertex')
            normal = GeomVertexWriter(vdata, 'normal')
            texcoord = GeomVertexWriter(vdata, 'texcoord')
            transform = GeomVertexWriter(vdata, 'transform_blend') 
            
            numtris = 0
            if type(controlled_prim.primitive) is collada.polylist.BoundPolygonList:
                for poly in controlled_prim.primitive.polygons():
                    for tri in poly.triangles():
                        for tri_pt in range(3):
                            vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                            normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                            if len(controlled_prim.primitive._texcoordset) > 0:
                                texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                            transform.addData1i(tri.indices[tri_pt])
                        numtris+=1
            elif type(controlled_prim.primitive) is collada.triangleset.BoundTriangleSet:
                for tri in controlled_prim.primitive.triangles():
                    for tri_pt in range(3):
                        vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                        normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                        if len(controlled_prim.primitive._texcoordset) > 0:
                            texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                        transform.addData1i(tri.indices[tri_pt])
                    numtris+=1
                        
            tbtable.setRows(SparseArray.lowerOn(vdata.getNumRows())) 
            
            gprim = GeomTriangles(Geom.UHStatic)
            for i in range(numtris):
                gprim.addVertices(i*3, i*3+1, i*3+2)
                gprim.closePrimitive()
                
            pgeom = Geom(vdata)
            pgeom.addPrimitive(gprim)
            
            render_state = getStateFromMaterial(controlled_prim.primitive.material, subfile_map)
            control_node = GeomNode("ctrlnode")
            control_node.addGeom(pgeom, render_state)
            ch.addChild(control_node)
        
            bundle = AnimBundle('simplechar', 5.0, 2)
            skeleton = AnimGroup(bundle, '<skeleton>')
            root = AnimChannelMatrixXfmTable(skeleton, 'root')

            wiggle = AnimBundleNode('wiggle', bundle)

            np = NodePath(ch) 
            anim = NodePath(wiggle) 
            a = Actor(np, {'simplechar' : anim})
            a.loop('simplechar') 
            return a
        
        else:
            raise Exception("Error: unsupported controller type")

def getNodeFromGeom(prim, subfile_map):
        format = GeomVertexFormat.getV3n3t2()
        vdata = GeomVertexData("dataname", format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        
        numtris = 0
        
        if type(prim) is collada.triangleset.BoundTriangleSet:
            for tri in prim.triangles():
                for tri_pt in range(3):
                    vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                    normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                    if len(prim._texcoordset) > 0:
                        texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                numtris+=1
                
        elif type(prim) is collada.polylist.BoundPolygonList:
            for poly in prim.polygons():
                for tri in poly.triangles():
                    for tri_pt in range(3):
                        vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                        normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                        if len(prim._texcoordset) > 0:
                            texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                    numtris+=1

        else:
            raise Exception("Error: Unsupported primitive type. Exiting.")
        
        gprim = GeomTriangles(Geom.UHStatic)
        for i in range(numtris):
            gprim.addVertices(i*3, i*3+1, i*3+2)
            gprim.closePrimitive()
            
        pgeom = Geom(vdata)
        pgeom.addPrimitive(gprim)
        
        render_state = getStateFromMaterial(prim.material, subfile_map)
        node = GeomNode("primitive")
        node.addGeom(pgeom, render_state)
        
        return node

def getStateFromMaterial(prim_material, subfile_map):
    state = RenderState.makeFullDefault()
    
    emission = None
    ambient = None
    diffuse = None
    specular = None
    shininess = None
    reflection = None
    reflectivity = None
    
    if prim_material:
        for prop in prim_material.supported:
            value = getattr(prim_material, prop)
            
            if value is None:
                continue
            
            if type(value) is tuple:
                val4 = value[3] if len(value) > 3 else 1.0
                value = VBase4(value[0], value[1], value[2], val4)
            
            if isinstance(value, collada.material.Map):
                texture_file = value.sampler.surface.image.path
                if not texture_file is None:
                    tex_base = os.path.basename(texture_file)
                    myImage = PNMImage()
                    myImage.read(StringStream(subfile_map[tex_base]), tex_base)
                    myTexture = Texture(texture_file)
                    myTexture.load(myImage)
                    state = state.addAttrib(TextureAttrib.make(myTexture))
            elif prop == 'emission':
                emission = value
            elif prop == 'ambient':
                ambient = value
            elif prop == 'diffuse':
                diffuse = value
            elif prop == 'specular':
                specular = value
            elif prop == 'shininess':
                shininess = value
            elif prop == 'reflective':
                reflective = value
            elif prop == 'reflectivity':
                reflectivity = value
            elif prop == 'transparent':
                pass
            elif prop == 'transparency':
                pass
            else:
                raise
    
    mat = Material()
    
    if not emission is None:
        mat.setEmission(emission)
    if not ambient is None:
        mat.setAmbient(ambient)
    if not diffuse is None:
        mat.setDiffuse(diffuse)
    if not specular is None:
        mat.setSpecular(specular)
    if not shininess is None:
        mat.setShininess(shininess)
        
    state = state.addAttrib(MaterialAttrib.make(mat))
    return state

@task
def generate_screenshot(filename, typeid):
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
        
    mesh = collada.Collada(StringIO(dae_data))
        
    #loadPrcFileData('', 'load-display tinydisplay')
    p3dApp = ShowBase()
    
    globNode = GeomNode("collada")
    nodePath = render.attachNewNode(globNode)
    
    for geom in mesh.scene.objects('geometry'):
        for prim in geom.primitives():
            node = getNodeFromGeom(prim, subfile_map)
            nodePath.attachNewNode(node)
    
    for controller in mesh.scene.objects('controller'):
        for controlled_prim in controller.primitives():
            a = getNodeFromController(controller, controlled_prim, subfile_map)
            a.reparentTo(nodePath)
    
    boundingSphere = nodePath.getBounds()
    scale = 5.0 / boundingSphere.getRadius()
    
    nodePath.setScale(scale, scale, scale)
    boundingSphere = nodePath.getBounds()
    nodePath.setPos(-1 * boundingSphere.getCenter().getX(),
                    -1 * boundingSphere.getCenter().getY(),
                    -1 * boundingSphere.getCenter().getZ())
    nodePath.setHpr(0,0,0)
    
    base.camera.setPos(10, -10, 0)
    base.camera.lookAt(0.0, 0.0, 0.0)
    
    base.setBackgroundColor(0.8,0.8,0.8)
    base.disableMouse()

    ambientLight = AmbientLight('ambientLight')
    ambientLight.setColor(Vec4(0.1, 0.1, 0.1, 1))
    ambientLightNP = render.attachNewNode(ambientLight)
    render.setLight(ambientLightNP)
    
    directionalPoints = [(10,0,0), (-10,0,0),
                         (0,-10,0), (0,10,0),
                         (0, 0, -10), (0,0,10)]
    
    for pt in directionalPoints:
        directionalLight = DirectionalLight('directionalLight')
        directionalLight.setColor(Vec4(0.4, 0.4, 0.4, 1))
        directionalLightNP = render.attachNewNode(directionalLight)
        directionalLightNP.setPos(pt[0], pt[1], pt[2])
        directionalLightNP.lookAt(0,0,0)
        render.setLight(directionalLightNP)
    
    taskMgr.step()
    pnmss = PNMImage()
    base.win.getScreenshot(pnmss)
    resulting_ss = StringStream()
    pnmss.write(resulting_ss, "screenshot.png")
    screenshot_buffer = resulting_ss.getData()
    
    im = Image.open(StringIO(screenshot_buffer))
    im.load()
    if 'A' in list(im.getbands()):
        bbox = im.split()[list(im.getbands()).index('A')].getbbox()
        im = im.crop(bbox)
    main_screenshot = StringIO()
    im.save(main_screenshot, "PNG")
    main_screenshot = main_screenshot.getvalue()
    
    thumbnail = StringIO()
    im.thumbnail((96,96), Image.ANTIALIAS)
    im.save(thumbnail, "PNG")
    thumbnail = thumbnail.getvalue()
    
    main_key = hashlib.sha256(main_screenshot).hexdigest()
    thumb_key = hashlib.sha256(thumbnail).hexdigest()
    save_file_data(main_key, main_screenshot, "image/png")
    save_file_data(thumb_key, thumbnail, "image/png")
    
    ss_info = {'screenshot': main_key, 'thumbnail': thumb_key}
    base_filename, version_num = os.path.split(filename)
    add_metadata(base_filename, version_num, typeid, ss_info)
    
    p3dApp.destroy()
    