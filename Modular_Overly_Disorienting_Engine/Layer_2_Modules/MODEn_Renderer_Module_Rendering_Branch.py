from OpenGL.GL import *
#TODO add documentation to like everything
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import purpose_text,CompleteShader,USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Texture_Module_Rendering_Branch import TextureHandler
from Modular_Overly_Disorienting_Engine.Layer_2_Modules.MODEn_Text_Module_Rendering_Branch import TextHandler
import numpy as np
purpose_text("Handles the rendering process of the camera. Dictates everything related to what objects each shader sees in what order")
PASS_MAIN="main_shader"
PASS_EXTRA="extra_shader"
PASS_POST_PROCESSING="post_processing_shader"
PASS_TEXT="text_shader"
PASS_TEXT_UI="text_ui_shader"
PASS_UI="ui_shader"
default_types_of_shader_passes=[PASS_MAIN,PASS_EXTRA,PASS_POST_PROCESSING,PASS_TEXT,PASS_TEXT_UI,PASS_UI]


def _resolve_ui_handler():
    """The UI module sits in Layer 4 and this renderer is Layer 2, so importing it
       at module scope would invert the layer order and deadlock the import graph.
       Looking it up lazily keeps the UI pass optional: an engine build without the
       UI module still renders everything else."""
    try:
        from Modular_Overly_Disorienting_Engine.Layer_4_Modules.MODEn_UI_Module_Rendering_Branch import UIHandler
    except Exception:
        return None
    return UIHandler


def _get_models_and_lights(entities:list):
    models,lights=[],[]
    for entity in entities:
        models.extend(entity._models)
        lights.extend(entity._lights)
    return models,lights
def naive_sphere_frustum_culling(camera): #TODO add more performant culling modes
    # A camera that only draws UI or text layers never needs a scene, so treat the
    # absence of one as "nothing in the world to cull" instead of an AttributeError.
    if camera.scene is None:
        return []
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
            if type_of_pass==PASS_UI:
                pass_type_to_set = self._ui_shader_pass
        else:
            pass_type_to_set=type_of_pass
        for shader in shaders:
            if shader not in self.shaders:
                self.shaders[shader] = {
                    "pass type": pass_type_to_set,
                    "models": {},
                    # Text and UI passes draw layers rather than models. An empty list
                    # means "every layer of my kind", which is what the passes used to
                    # assume; filling it in restricts a shader to specific layers, so a
                    # world-space text shader and a UI text shader can coexist on one
                    # camera without each drawing the other's layers.
                    "layers": []
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
    def _add_layers_to_shader(self, shaders, layers):
        """Binds specific text or UI layers to a shader, the way _add_models_to_shader
           binds models. Leave a shader with no layers attached and it falls back to
           drawing every layer of its kind."""
        if not isinstance(shaders, list): shaders = [shaders]
        if not isinstance(layers, list): layers = [layers]
        for shader in shaders:
            if shader not in self.shaders:
                continue
            attached = self.shaders[shader]["layers"]
            for layer in layers:
                if layer not in attached:
                    attached.append(layer)

    def _layers_for(self, shader, all_layers):
        attached = self.shaders[shader].get("layers")
        return attached if attached else all_layers

    def _reorder_shaders(self,shader,new_index,swap_instead_of_move:bool): #TODO add index = 0 protection
        if shader in self.shader_order:
            self.shader_order.remove(shader)
            if not swap_instead_of_move:
                self.shader_order.insert(new_index,shader)
            else:
                self.shader_order.insert(new_index, shader)
                self._reorder_shaders(shader,len(self.shader_order),False)
    def _render(self,camera,renderables=None):
        """Draws every shader pass in order.

           The camera already has to cull once per frame to work out how many lights
           are visible, so it passes that result straight in rather than making us
           repeat the whole frustum test."""
        if renderables is None:
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

    def _draw_layers(self, shader, camera, layers, storage_buffer, binding_point, supply_camera_uniforms):
        """The shared body of every layer pass.

           Text and UI layers are drawn the same way: one unit quad, instanced once per
           packed struct, with the shader reading its per-instance data out of an SSBO at
           gl_InstanceID + u_buffer_offset. The only differences between the passes are
           which buffer is bound, which binding point it goes to, and whether the camera
           gets a say in the matrices."""
        quad = TextHandler._GLOBAL_TEXT_QUAD
        if quad is None or not storage_buffer:
            return
        quad_vao = quad.get_mesh_instance().mesh.VAO
        shader.use()
        for layer in layers:
            instance_count = layer.get_character_count() if hasattr(layer, "get_character_count") \
                else layer.get_rect_count()
            if instance_count <= 0:
                continue

            # Only 16 textures can be visible to one draw call, so tell the texture
            # handler which ones this layer actually needs before drawing it.
            wanted_slots = layer.get_used_texture_slots()
            if wanted_slots:
                TextureHandler.ensure_resident(wanted_slots)

            shader.set_uniform(["u_buffer_offset"], [layer.buffer_offset])
            if supply_camera_uniforms:
                shader.set_uniform(*camera.get_uniforms(shader.wanted_uniforms))
            # The layer goes last so that its own orthographic matrix wins over the
            # camera's perspective one when both supply the same uniform name.
            shader.set_uniform(*layer.get_uniforms(shader.wanted_uniforms))

            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, binding_point, storage_buffer)
            glBindVertexArray(quad_vao)
            glDrawElementsInstanced(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None, instance_count)
            glBindVertexArray(0)

    def _text_shader_pass(self, shader, camera, renderables):
        """Text that lives in the world: it sits at real coordinates and is occluded by
           geometry in front of it."""
        if not TextHandler.text_layers:
            return
        layers = self._layers_for(shader, TextHandler.text_layers)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Glyph quads sit in the same plane and overlap along their edges. Writing depth
        # would let whichever glyph drew first clip its neighbour's antialiased border,
        # leaving visible seams, so the pass tests depth but does not write it.
        glDepthMask(GL_FALSE)
        shader.use()
        shader.set_uniform(["u_distance_range"], [float(TextHandler.distance_range)])
        self._draw_layers(shader, camera, layers, TextHandler.text_shader_storage_buffer, 2, True)
        glDepthMask(GL_TRUE)

    def _text_ui_shader_pass(self, shader, camera, renderables):
        """Text pinned to the screen. Draws on top of everything, so the depth buffer is
           out of the picture entirely and the layer's own orthographic matrix positions
           the glyphs in pixels."""
        if not TextHandler.text_layers:
            return
        layers = self._layers_for(shader, TextHandler.text_layers)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        shader.use()
        shader.set_uniform(["u_distance_range"], [float(TextHandler.distance_range)])
        self._draw_layers(shader, camera, layers, TextHandler.text_shader_storage_buffer, 2, False)
        glEnable(GL_DEPTH_TEST)

    def _ui_shader_pass(self, shader, camera, renderables):
        """The widget rectangles behind the UI text: panels, window frames, buttons.
           Runs before the UI text pass so that captions land on top of their widget,
           which is down to shader ordering on the camera, not to anything here."""
        ui_handler = _resolve_ui_handler()
        if ui_handler is None or not getattr(ui_handler, "ui_layers", None):
            return
        layers = self._layers_for(shader, ui_handler.ui_layers)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        self._draw_layers(shader, camera, layers, ui_handler.ui_shader_storage_buffer,
                          ui_handler.UI_BUFFER_BINDING, False)
        glEnable(GL_DEPTH_TEST)
