from OpenGL.GL import *
#TODO add documentation to like everything
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import purpose_text,CompleteShader,USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_2_Modules.MODEn_Text_Module_Rendering_Branch import TextHandler
import numpy as np
purpose_text("Handles the rendering process of the camera. Dictates everything related to what objects each shader sees in what order")
PASS_MAIN="main_shader"
PASS_EXTRA="extra_shader"
PASS_POST_PROCESSING="post_processing_shader"
PASS_TEXT="text_shader"
PASS_TEXT_UI="text_ui_shader"
default_types_of_shader_passes=[PASS_MAIN,PASS_EXTRA,PASS_POST_PROCESSING,PASS_TEXT,PASS_TEXT_UI]


def _get_models_and_lights(entities:list):
    models,lights=[],[]
    for entity in entities:
        models.extend(entity._models)
        lights.extend(entity._lights)
    return models,lights
def naive_sphere_frustum_culling(camera): #TODO add more performant culling modes
    renderable_entities=camera.scene.get_renderable_entities()
    renderables_in_view=[]
    models,lights=_get_models_and_lights(renderable_entities)
    for model in models:
        if camera.model_in_view(model):
            renderables_in_view.append(model)
    for light in lights:
        if camera.light_in_view(light):
            renderables_in_view.append(light)
    return renderables_in_view

CULLING_NAIVE_FRUSTUM="culling_naive_frustsum"
class Renderer:
    culling_dict={CULLING_NAIVE_FRUSTUM:naive_sphere_frustum_culling}
    def __init__(self):
        self.shader_order=[]
        self.shaders={}
        self.culling_method = None

    def _add_shader(self, shaders:list|CompleteShader,type_of_pass,index:int=USE_OWN,swap_instead_of_move=False):
        pass_type_to_set=None
        if type(shaders)!=list:
            shaders=[shaders]
        if type_of_pass in default_types_of_shader_passes:
            if type_of_pass==PASS_EXTRA:
                pass_type_to_set=self._extra_shader_pass
            if type_of_pass == PASS_MAIN:
                pass_type_to_set = self._main_shader_pass
            if type_of_pass==PASS_POST_PROCESSING:
                pass_type_to_set=self._post_processing_shader_pass
            if type_of_pass==PASS_TEXT:
                pass_type_to_set=self._text_shader_pass
            if type_of_pass==PASS_TEXT_UI:
                pass_type_to_set = self._text_ui_shader_pass
        else:
            pass_type_to_set=type_of_pass
        for shader in shaders:
            if shader not in self.shaders:
                self.shaders[shader] = {
                    "pass type": pass_type_to_set,
                    "models": {}
                }
                if index != USE_OWN:
                    self._reorder_shaders(shader, index, swap_instead_of_move)
                else:
                    self.shader_order.append(shader)

    def _add_models_to_shader(self, shaders, models):
        """Groups models by their Mesh resource for the given shaders.
           This is in preparation for batching. Maybe"""
        if not isinstance(shaders, list): shaders = [shaders]
        if not isinstance(models, list): models = [models]

        for shader in shaders:

            group_dict = self.shaders[shader]["models"]
            for model in models:
                mesh_key = model.get_mesh_instance().mesh
                if mesh_key not in group_dict:
                    group_dict[mesh_key] = []
                if model not in group_dict[mesh_key]:
                    group_dict[mesh_key].append(model)
    def _reorder_shaders(self,shader,new_index,swap_instead_of_move:bool): #TODO add index = 0 protection
        if shader in self.shader_order:
            self.shader_order.remove(shader)
            if not swap_instead_of_move:
                self.shader_order.insert(new_index,shader)
            else:
                self.shader_order.insert(new_index, shader)
                self._reorder_shaders(shader,len(self.shader_order),False)
    def _render(self,camera):
        renderables=self.culling_method(camera)
        for shader in self.shader_order:
            self.shaders[shader]["pass type"](shader,camera,renderables)
    def _set_culling_mode(self,culling_mode):
        self.culling_method=Renderer.culling_dict[culling_mode]
    def _main_shader_pass(self,shader, camera, renderables):
        shader.use()
        shader.set_uniform(*camera.get_uniforms(shader.wanted_uniforms))

        mesh_groups = self.shaders[shader]["models"]

        for mesh, instances in mesh_groups.items():
            active_instances = [m for m in instances if m in renderables]
            if not active_instances:
                continue
            if len(active_instances) == 1:
                model = active_instances[0]
                shader.set_uniform(*model.get_uniforms(shader.wanted_uniforms))
                model.draw()
            else:
                glBindVertexArray(mesh.VAO)
                for model in active_instances:
                    shader.set_uniform(*model.get_uniforms(shader.wanted_uniforms))
                    glDrawElements(GL_TRIANGLES, mesh.indice_length, GL_UNSIGNED_INT, None)

                glBindVertexArray(0)


    def _extra_shader_pass(self,shader,camera,renderables):
        shader.use()
        shader.set_uniform(*camera.get_uniforms(shader.wanted_uniforms))

        mesh_groups = self.shaders[shader]["models"]

        for mesh, instances in mesh_groups.items():
            active_instances = [m for m in instances if m in renderables]
            if not active_instances:
                continue
            if len(active_instances) == 1:
                model = active_instances[0]
                shader.set_uniform(*model.get_uniforms(shader.wanted_uniforms))
                model.draw()
            else:
                glBindVertexArray(mesh.VAO)
                for model in active_instances:
                    shader.set_uniform(*model.get_uniforms(shader.wanted_uniforms))
                    glDrawElements(GL_TRIANGLES, mesh.indice_length, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)

    @staticmethod
    def _post_processing_shader_pass(shader,camera,renderables):
        pass

    @staticmethod
    def _text_shader_pass(shader,camera,renderables):  #TODO add layers as the renderable
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        for layer in TextHandler.text_layers:
            layer_char_count = sum(p['char_count'] for p in layer.paragraphs)
            if layer_char_count > 0:
                shader.use()
                shader.set_uniform(["u_buffer_offset"], [layer.buffer_offset])
                shader.set_uniform(*camera.get_uniforms(shader.wanted_uniforms))
                shader.set_uniform(*layer.get_uniforms(shader.wanted_uniforms))
                glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)
                glBindVertexArray(TextHandler._GLOBAL_TEXT_QUAD.get_mesh_instance().mesh.VAO)
                glDrawElementsInstanced(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None, layer_char_count)
                glBindVertexArray(0)

    @staticmethod
    def _text_ui_shader_pass(shader, camera, renderables):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        for layer in renderables:

            pass

            # shader.use()
            # shader.set_uniform(["u_buffer_offset"], [layer.buffer_offset])
            # shader.set_uniform(*camera.get_uniforms(shader.wanted_uniforms))
            # shader.set_uniform(*layer.get_uniforms(shader.wanted_uniforms))
            # glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)
            # glBindVertexArray(TextHandler._GLOBAL_TEXT_QUAD.get_mesh_instance().mesh.VAO)
            # glDrawElementsInstanced(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None, layer_char_count)
            # glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)