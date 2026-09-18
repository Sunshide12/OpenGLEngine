from pyglm import glm
from OpenGL.GL import *
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import purpose_text,USE_OWN,UniformHelper,Entity,ENTITY_TYPE_MODEL
import numpy as np
purpose_text("Handles the rudimentary containers of Meshes (unique shapes+data), MeshInstances(shared meshes across models) and Models(containers for mesh instances + physical data)")
# the ComplexModel class is the main thing that you maneuver around. It encompasses as many SimpleModel objects as it wants.
# not yet added
debug=True
class Mesh:
    def __init__(self):
        self.vertices = []
        self.indices = []
        self.attributes = [3]
        self.attributes_type = [float]
        self.stride = 12

        self.VAO = glGenVertexArrays(1)
        self.VBO = glGenBuffers(1)
        self.EBO = glGenBuffers(1)
        self.indice_length = 0

        self.local_aabb = [np.zeros(3), np.zeros(3)]
        self.bounding_radius = 0.0

    def add_data(self, vertices: list = None, indices: list = None,auto_upload=True):
        if vertices:
            self.vertices.extend(vertices)
        if indices:
            self.indices.extend(indices)
            self.indice_length = len(self.indices)
        if auto_upload:
            self.upload()
    def set_data(self, vertices: list, indices: list):
        self.vertices = vertices
        self.indices = indices
        self.indice_length = len(self.indices)

    def add_attribute(self, count: int, attr_type=float):
        self.attributes.append(count)
        self.attributes_type.append(attr_type)
        self.stride = sum(self.attributes) * 4

    def upload(self, recalculate_aabb: bool = True):
        if not self.vertices: return


        dtype_fields = []
        for i, (count, a_type) in enumerate(zip(self.attributes, self.attributes_type)):
            type_code = 'f4' if a_type == float else 'u4'
            dtype_fields.append((f'attr{i}', type_code, (count,)))

        total_components = sum(self.attributes)
        vertex_count = len(self.vertices) // total_components
        reshaped_data = np.array(self.vertices).reshape(vertex_count, total_components)

        structured_verts = np.empty(vertex_count, dtype=dtype_fields)
        curr_col = 0
        for i, count in enumerate(self.attributes):
            structured_verts[f'attr{i}'] = reshaped_data[:, curr_col:curr_col + count]
            curr_col += count

        indices_np = np.array(self.indices, dtype=np.uint32)


        glBindVertexArray(self.VAO)

        glBindBuffer(GL_ARRAY_BUFFER, self.VBO)
        glBufferData(GL_ARRAY_BUFFER, structured_verts.nbytes, structured_verts, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.EBO)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_np.nbytes, indices_np, GL_STATIC_DRAW)


        offset = 0
        for i, (count, a_type) in enumerate(zip(self.attributes, self.attributes_type)):
            glEnableVertexAttribArray(i)
            if a_type == float:
                glVertexAttribPointer(i, count, GL_FLOAT, GL_FALSE, self.stride, ctypes.c_void_p(offset))
            else:
                glVertexAttribIPointer(i, count, GL_UNSIGNED_INT, self.stride, ctypes.c_void_p(offset))
            offset += count * 4

        glBindVertexArray(0)
        if recalculate_aabb: self._update_local_aabb()

    def _update_local_aabb(self):
        verts = np.array(self.vertices, dtype=np.float32).reshape(-1, sum(self.attributes) // 1)[:, :3]
        min_pt = np.min(verts, axis=0)
        max_pt = np.max(verts, axis=0)
        self.local_aabb = [min_pt, max_pt]
        center = (min_pt + max_pt) * 0.5
        self.bounding_radius = np.max(np.linalg.norm(verts - center, axis=1))
class MeshInstance:
    def __init__(self, mesh_resource: Mesh):
        self.mesh = mesh_resource
        self.world_aabb = [np.zeros(3), np.zeros(3)]

    def get_mesh(self):
        return self.mesh

    def draw(self):
        glBindVertexArray(self.mesh.VAO)
        glDrawElements(GL_TRIANGLES, self.mesh.indice_length, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def calculate_world_aabb(self, model_matrix):
        min_pt, max_pt = self.mesh.local_aabb
        corners = np.array([
            [min_pt[0], min_pt[1], min_pt[2], 1], [max_pt[0], min_pt[1], min_pt[2], 1],
            [min_pt[0], max_pt[1], min_pt[2], 1], [max_pt[0], max_pt[1], min_pt[2], 1],
            [min_pt[0], min_pt[1], max_pt[2], 1], [max_pt[0], min_pt[1], max_pt[2], 1],
            [min_pt[0], max_pt[1], max_pt[2], 1], [max_pt[0], max_pt[1], max_pt[2], 1]
        ])
        transformed = (np.array(model_matrix) @ corners.T).T[:, :3]
        self.world_aabb = [np.min(transformed, axis=0), np.max(transformed, axis=0)]
        return self.world_aabb
class ModelHandler:
    make_entitiy_when_creating_model=True
class Model:
    IDENTITY_M4 = glm.mat4(1.0)

    def __init__(self, mesh: Mesh = None, autoadd_to_main_scene=True,entity=None,make_entity=ModelHandler.make_entitiy_when_creating_model,parent=None, autorender=True):

        self._mesh_instance = MeshInstance(mesh if mesh else Mesh())
        self._position_global = glm.vec3(0.0)
        self._rotation_global = glm.vec3(0.0)
        self._position_relative=glm.vec3(0.0)
        self._rotation_relative=glm.vec3(0.0)
        self._scale_global = glm.vec3(1.0)
        self._scale_relative = glm.vec3(1.0)
        self._model_matrix = glm.mat4(1.0)
        self._normal_matrix = glm.mat3(1.0)
        self._rotation_matrix = glm.mat4(1.0)
        self._changed = True
        self._uniform_helper = UniformHelper()
        self.set_uniforms("normal_matrix", self.get_normal_matrix)
        self.set_uniforms("model_matrix", self.get_model_matrix)
        self._parent=parent
        self._children=[]
        if make_entity and entity is None:
            entity=Entity(models=self,entity_type=ENTITY_TYPE_MODEL)
        self._entity = entity
    def set_uniforms(self, names, values, struct=None):
        self._uniform_helper._set_uniforms(names, values, struct)
    def get_uniforms(self, names):
        return self._uniform_helper._get_uniforms(names)
    def get_all_uniform_names(self):
        return self._uniform_helper._get_all_uniform_names()
    def get_world_aabb(self):
        return self._mesh_instance.calculate_world_aabb(self.get_model_matrix())
    def update_matrices(self):
        if not self._changed: return
        rad = glm.radians(self.get_rotation())

        rot = glm.rotate(self.IDENTITY_M4, rad.y, glm.vec3(0, 1, 0))
        rot = glm.rotate(rot, rad.x, glm.vec3(1, 0, 0))
        self._rotation_matrix = glm.rotate(rot, rad.z, glm.vec3(0, 0, 1))

        m = glm.translate(self.IDENTITY_M4, self.get_position())
        m = m * self._rotation_matrix
        self._model_matrix = glm.scale(m, self.get_scale())

        if all(s == 1.0 for s in self._scale_global):
            self._normal_matrix = glm.mat3(self._model_matrix)
        else:
            self._normal_matrix = glm.inverseTranspose(glm.mat3(self._model_matrix))
        self._changed = False
    def get_model_matrix(self):
        self.update_matrices()
        return self._model_matrix
    def get_normal_matrix(self):
        self.update_matrices()
        return self._normal_matrix
    def add_vertices(self, vertices: list,upload_data_to_gpu=True):
        self._mesh_instance.mesh.add_data(vertices=vertices,auto_upload=upload_data_to_gpu)
    def connect_vertices(self, indices: list,upload_data_to_gpu=True):
        self._mesh_instance.mesh.add_data(indices=indices,auto_upload=upload_data_to_gpu)
    def add_attribute(self, count: int, attr_type=float):
        self._mesh_instance.mesh.add_attribute(count, attr_type)
    def draw(self):
        self._mesh_instance.draw()
    def get_bounding_radius(self):
        return self._mesh_instance.mesh.bounding_radius

    def get_mesh_instance(self):
        return self._mesh_instance
    def set_mesh(self, mesh_resource: Mesh):
        self._mesh_instance = MeshInstance(mesh_resource)




    def set_position(self, x=USE_OWN, y=USE_OWN, z=USE_OWN,relative_to_self=True):
        if relative_to_self:
            px,py,pz=0,0,0
        else:
            px,py,pz=self.get_parent().get_position()
        if x != USE_OWN:
            self._position_relative.x = x
            self._position_global.x = x+px
        if y != USE_OWN:
            self._position_relative.y = y
            self._position_global.y = y+py
        if z != USE_OWN:
            self._position_relative.z = z
            self._position_global.z = z+pz
        self._changed = True
    def set_rotation(self, pitch=USE_OWN, yaw=USE_OWN, roll=USE_OWN, relative_to_self=True):  # TODO maybe add quats for rotation
        if relative_to_self:
            pp, py, pr = 0, 0, 0
        else:
            pp, py, pr = self.get_parent().get_rotation()
        if pitch != USE_OWN:
            self._rotation_relative.x = pitch
            self._rotation_global.x = pitch + pp
        if yaw != USE_OWN:
            self._rotation_relative.y = yaw
            self._rotation_global.y = yaw + py
        if roll != USE_OWN:
            self._rotation_relative.z = roll
            self._rotation_global.z = roll + pr
        self._changed = True
    def set_scale(self, x=USE_OWN, y=USE_OWN, z=USE_OWN, relative_to_self=True):
        if relative_to_self:
            px, py, pz = 0, 0, 0
        else:
            px, py, pz = self.get_parent().get_scale()
        if x != USE_OWN:
            self._scale_relative.x = x
            self._scale_global.x = x + px
        if y != USE_OWN:
            self._scale_relative.y = y
            self._scale_global.y = y + py
        if z != USE_OWN:
            self._scale_relative.z = z
            self._scale_global.z = z + pz
        self._changed = True


    def change_position(self, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
        target = self.get_parent() if relative_to == USE_OWN else relative_to
        origin = target.get_position()

        if change_vectorially:
            rot_context = target.get_rotation_matrix()
            offset = glm.vec3(x, y, z)
            direction = glm.vec3(rot_context * glm.vec4(offset, 0.0))
            new_pos = origin + direction
        else:
            new_pos = origin + glm.vec3(x, y, z)
        if target == self:
            relative_to_self=True
        else:
            relative_to_self=False
        self.set_position(new_pos.x, new_pos.y, new_pos.z,relative_to_self)
    def change_rotation(self, pitch=0, yaw=0, roll=0, relative_to=USE_OWN, rotate_around_self=False):
        """
        Increments rotation.
        If rotate_around_relative is True and relative_to is another object,
        this object will orbit around that target.
        """
        rel_rot = self.get_parent().get_rotation() if relative_to == USE_OWN else relative_to.get_rotation()
        self.set_rotation(rel_rot.x + pitch, rel_rot.y + yaw, rel_rot.z + roll,rotate_around_self)
        if not rotate_around_self and relative_to != USE_OWN:
            pivot = relative_to.get_position()
            current_pos = self.get_position()
            offset = current_pos - pivot
            rad = glm.radians(glm.vec3(pitch, yaw, roll))

            rot = glm.rotate(self.IDENTITY_M4, rad.y, glm.vec3(0, 1, 0))  # yaw
            rot = glm.rotate(rot, rad.x, glm.vec3(1, 0, 0))  # pitch
            rot_matrix = glm.rotate(rot, rad.z, glm.vec3(0, 0, 1))

            rotated_offset = glm.vec3(rot_matrix * glm.vec4(offset, 1.0))
            new_pos = pivot + rotated_offset
            self.set_position(new_pos.x, new_pos.y, new_pos.z)
    def change_scale(self, x=0, y=0, z=0, relative_to=USE_OWN):

        rel = self._parent.get_scale() if relative_to == USE_OWN else relative_to.get_scale()
        if rel == self:
            relative_to_self=True
        else:
            relative_to_self=False
        self.set_scale(rel[0] + x, rel[1] + y, rel[2] + z,relative_to_self)




    def get_position(self):
        return self._position_global

    def get_rotation(self):
        return self._rotation_global
    def get_scale(self):
        return self._scale_global
    def get_rotation_matrix(self):
        self.update_matrices()
        return self._rotation_matrix
    def get_entity(self):
        return self._entity

    def get_parent(self):
        return self._parent if self._parent is not None else self
    def add_children(self,children):
        if not isinstance(children,list):
            children=[children]
        self._children.extend(children)
        self.get_entity().add_models(children)
    def set_parent(self,new_parent):
        self.orphan_self()
        self._parent=new_parent
        self._parent.add_children(self)
    def orphan_self(self):
        if self._parent:
            self._parent.orphan_children(self)
    def orphan_children(self,children):
        if not isinstance(children,list):
            children=[children]
        for child in children:
            self._children.remove(child)
class Anchor:
    def __init__(self):
        pass
WorldAnchor=Anchor()