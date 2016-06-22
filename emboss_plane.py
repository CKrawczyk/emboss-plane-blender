bl_info = {
    "name": "Emboss plane",
    "description": "Emboss and solidify a plane",
    "author": "Coleman Krawczyk",
    "version": (1, 0),
    "blender": (2, 76, 0),
    "location": "View3D > Tools > Mesh Edit",
    "category": "Mesh",
}

import bpy
import bmesh
import math
from bpy.props import IntProperty, FloatProperty

def findConnectedVerts(vert_list, bm, maxdepth=1, level=0):
    if level >= maxdepth:
        return vert_list
    vert_list_new = []
    for edge in bm.edges:
        for vert in edge.verts:
            if vert in vert_list:
                vert_list_new += edge.verts
                break
    #remove doubles
    vert_list_new = list(set(vert_list_new))
    vert_list_out = findConnectedVerts(vert_list_new, bm, maxdepth=maxdepth, level=level+1)
    return vert_list_out

class EmbossPlane(bpy.types.Operator):
    """Emboss Plane"""
    bl_idname = "object.emboss_plane"
    bl_label = "Emboss and solidify a plane"
    bl_options = {'REGISTER', 'UNDO'}

    B = IntProperty(name="Number of faces", default=1000, min=0, description="Number of faces across the top of the plane")
    Height = FloatProperty(name="Thickness", default=0.2, unit="LENGTH", description="Thickness of the base")
    Border_width = IntProperty(name="Border width", default=2, min=1, description="Width (in boxes) of the border")

    def execute(self, context):
        object = context.active_object

        # get object
        bm = bmesh.from_edit_mesh(object.data)
        if hasattr(bm.verts, "ensure_lookup_table"):
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

        # get length and width
        lx = bm.edges[0].calc_length()
        ly = bm.edges[1].calc_length()

        # get number of cuts to make
        A = lx/ly
        nx = round(math.sqrt(A*self.B)) - 1
        ny = round(math.sqrt(self.B/A)) - 1

        # make loop cuts
        bpy.ops.mesh.loopcut_slide(MESH_OT_loopcut={"number_cuts":nx, "edge_index":0})
        bpy.ops.mesh.loopcut_slide(MESH_OT_loopcut={"number_cuts":ny, "edge_index":1})
        bpy.ops.mesh.select_all(action='TOGGLE')

        # make vertex groups
        #bound = [v.index for v in bm.verts if v.is_boundary]
        #face = [v.index for v in bm.verts if not v.is_boundary]
        boundary = [v for v in bm.verts if v.is_boundary]
        near_bound = findConnectedVerts(boundary, bm, maxdepth=self.Border_width)
        bound = [v.index for v in near_bound]
        face = [v.index for v in bm.verts if v.index not in bound]
        vgk = object.vertex_groups.keys()
        if 'boundary' not in vgk:
            object.vertex_groups.new('boundary')
        if 'face' not in vgk:
            object.vertex_groups.new('face')
        bpy.ops.object.editmode_toggle()
        object.vertex_groups['boundary'].add(bound, 1, 'REPLACE')
        object.vertex_groups['face'].add(face, 1, 'REPLACE')
        bpy.ops.object.editmode_toggle()

        # Extrude down and close bottom
        bm = bmesh.from_edit_mesh(object.data)
        if hasattr(bm.verts, "ensure_lookup_table"):
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
        extrude_normal = bm.verts[0].normal * -1 * self.Height
        bound_edges = [e for e in bm.edges if e.is_boundary]
        bound_edges_index = [e.index for e in bound_edges]
        bmesh.ops.extrude_edge_only(bm, edges=bound_edges)
        if hasattr(bm.verts, "ensure_lookup_table"):
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
        bound_verts = [v for v in bm.verts if v.is_boundary]
        bound_edges = [e for e in bm.edges if e.is_boundary]
        bound_edges_index += [e.index for e in bound_edges]
        bmesh.ops.translate(bm, vec=extrude_normal, verts=bound_verts)
        bmesh.ops.edgeloop_fill(bm, edges=bound_edges)

        # set crease on boundary
        bpy.ops.object.editmode_toggle()
        for idx in bound_edges_index:
            object.data.edges[idx].select = True
        bpy.ops.object.editmode_toggle()
        bpy.ops.transform.edge_crease(value=1)

        # add modifiers
        tex = bpy.data.textures.keys()
        mod = object.modifiers.keys()
        if 'Displacement' not in tex:
            iTex = bpy.data.textures.new('Displacemnt', type='IMAGE')
            iTex.image = bpy.data.images[-1] #assume last image loaded is the correct one
        if 'bump' not in mod:
            displace = object.modifiers.new(name='bump', type='DISPLACE')
            displace.texture = iTex
            displace.mid_level = 1
            displace.direction = 'Z'
            displace.vertex_group = 'face'
            displace.texture_coords = 'UV'
            displace.strength = .75 * self.Height
            displace.show_in_editmode = True
        else:
            displace = object.modifiers['bump']
            displace.strength = .75 * self.Height
        if 'smooth' not in mod:
            subsurf = object.modifiers.new(name='smooth', type='SUBSURF')
            subsurf.show_viewport = False
            subsurf.levels = 2

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        object = context.active_object
        sx, sy, sz = object.scale
        good = sx == sy == sz
        good = good and object is not None
        good = good and object.mode == 'EDIT'
        return good

def add_object_button(self, context):
    self.layout.operator(EmbossPlane.bl_idname, text=EmbossPlane.__doc__)

def register():
    bpy.utils.register_class(EmbossPlane)
    bpy.types.VIEW3D_PT_tools_meshedit.append(add_object_button)

def unregister():
    bpy.utils.unregister_class(EmbossPlane)

if __name__ == "__main__":
    register()
