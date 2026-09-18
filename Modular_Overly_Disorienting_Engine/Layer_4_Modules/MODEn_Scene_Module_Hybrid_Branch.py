import numpy as np
from OpenGL.GL import *

from Modular_Overly_Disorienting_Engine import purpose_text
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Physics_Body_Physics_Branch import BEHAVIOUR_DYNAMIC,BEHAVIOUR_HYBRID,BEHAVIOUR_STATIC,BEHAVIOUR_NONE
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Entity_Module_Hybrid_Branch import Entity

class SceneHandler:
    active_scenes = []
    inactive_scenes=[]
    @staticmethod
    def update_scenes(dt):
        for scene in SceneHandler.active_scenes:
            scene.update(dt)
class Scene:
    def __init__(self,autoactivate=True):
        self.active_entities=[]
        self.hybrid_entities_active = []
        self.hybrid_entities_inactive=[]
        self.static_entities = []
        self.deactivated_entities=[]
        self.renderables=[]
        if autoactivate:
            SceneHandler.active_scenes.append(self)


    def add_to_scene(self,entities:list|Entity):#TODO fix so is good and prevents passing incorrect types

        if not isinstance(entities,list):
            entities=[entities]
        assignment_dict={BEHAVIOUR_STATIC:self.static_entities,
                         BEHAVIOUR_HYBRID:self.hybrid_entities_active,
                         BEHAVIOUR_DYNAMIC:self.active_entities,
                         BEHAVIOUR_NONE:self.deactivated_entities,}
        for entity in entities:
            if not isinstance(entity,Entity):
                entity=entity.get_entity()
            for camera in entity.get_camera_list():
                if camera is not None:
                    camera.set_scene(self)
            assignment_dict[entity.get_physics_body_type()].append(entity)
        self.update_renderables()
    def update(self,dt):
        pass #TODO ACTUALLY UPDATE ENTITIES
    def update_renderables(self):
        self.renderables=[]    #TODO this is actually ass find a way to do rendering better than the naive approach
        self.renderables.extend(self.active_entities)
        self.renderables.extend(self.hybrid_entities_active)
        self.renderables.extend(self.hybrid_entities_inactive)
        self.renderables.extend(self.static_entities)
    def get_renderable_entities(self):
        return self.renderables


# class DebugScene:
#
#     total_scenes = 0
#
#     def __init__(self, starting_settings: SceneStartupSettings = active_startup_settings):
#         if isinstance(starting_settings, StartupSettings):
#             starting_settings = starting_settings.scene_startup
#         elif isinstance(starting_settings, SceneStartupSettings):
#             starting_settings = starting_settings
#         else:
#             raise TypeError("Expected Settings or SceneStartupSettings, got {}".format(type(starting_settings)))
#         DebugScene.active_scenes.append(self)
#         self.cameras = []
#         self.static_models = []
#         self.static_models_batch_vbo = glGenBuffers(1)
#         self.static_models_batch_vao = glGenVertexArrays(1)
#         self.vertex_attributes_for_static_models = starting_settings.vertex_attributes_for_static_models
#         self.dynamic_models = []
#         self.id = DebugScene.total_scenes
#
#         DebugScene.total_scenes += 1
#
#     def _reconfigure_static_object_batch_vao(self, vertices):
#         glBindVertexArray(self.static_models_batch_vao)
#         glBindBuffer(GL_ARRAY_BUFFER, self.static_models_batch_vbo)
#         glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
#         stride = sum(self.vertex_attributes_for_static_models) * 4  # bytes
#         offset = 0
#         for place, attribute in enumerate(self.vertex_attributes_for_static_models):
#             glVertexAttribPointer(place, attribute, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(offset * 4))
#             glEnableVertexAttribArray(place)
#             offset += attribute
#         glBindBuffer(GL_ARRAY_BUFFER, 0)
#
#     def _update(self):
#         for camera in self.cameras:
#             camera._update_clip_matrix()
#             camera._update_frustum_planes()
#
#     # def recalculate_static_batch_vbo(self):
#     #     total_vertex_data=[]
#     #     for model in self.static_models:
#     #         model_vert_data=model.mesh.get_vertex_data()
#     #         if sum(model.mesh.attributes)==sum(self.vertex_attributes_for_static_models):
#     #             total_vertex_data.extend(model_vert_data)
#     #         else:
#     #             raise ValueError(f"Vertex data of model {model} does not only contain position")
#     #     glBindBuffer(GL_ARRAY_BUFFER, self.static_models_batch_vbo)
#     #     vertices = np.array(total_vertex_data, dtype=np.float32)
#     #     glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
#     #     self._reconfigure_static_object_batch_vao(vertices)
#     #     glBindBuffer(GL_ARRAY_BUFFER, 0)
#
#     def add_static_object(self, static_object):
#         self.static_models.append(static_object)
#         static_object.update_rendering_area()
#
#         # self.recalculate_static_batch_vbo()
#
#     def add_to_scene(self, what: Model | Camera, model_import_as_static=True):
#         if type(what) == Model and what not in self.static_models:
#             if model_import_as_static:
#                 debug_text("BATCH RENDERING FOR STATIC OBJECTS WITH AABB CULLING IS BROKEN\n"
#                            "IN FAVOR OF INDIVIDUAL AABB CULLING.\n"
#                            "PLEASE FIX AT A LATER DATE")
#                 self.add_static_object(what)
#
#         if type(what) == Camera and what not in self.static_models:
#             self.cameras.append(what)
#             if what.scene is not None:
#                 what.scene.cameras.remove(what)
#             what.scene = self