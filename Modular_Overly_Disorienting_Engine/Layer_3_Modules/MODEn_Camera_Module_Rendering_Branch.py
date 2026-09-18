
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import *
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Shader_Module_Rendering_Branch import UniformHelper,TextureHandler
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Lighting_Module_Rendering_Branch import LightHandler, Light
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
from Modular_Overly_Disorienting_Engine.Layer_2_Modules import Renderer, PASS_MAIN, CULLING_NAIVE_FRUSTUM
import numpy as np
from pyglm import glm
#TODO ADD THE ABILITY TO HAVE ORTHO CAMERA
purpose_text("Handles math behind cameras")


AXIS_YAW =(0.0 ,1.0 ,0.0)
AXIS_PITCH =(1.0 ,0.0 ,0.0)
AXIS_ROLL =(0.0 ,0.0 ,1.0)

CAM_ROTATION_ORDER_YPR = (AXIS_ROLL, AXIS_PITCH, AXIS_YAW)
CAM_ROTATION_ORDER_YRP = (AXIS_PITCH, AXIS_ROLL, AXIS_YAW)
CAM_ROTATION_ORDER_RYP = (AXIS_PITCH, AXIS_YAW, AXIS_ROLL)
CAM_ROTATION_ORDER_RPY = (AXIS_YAW, AXIS_PITCH, AXIS_ROLL)
CAM_ROTATION_ORDER_PRY = (AXIS_YAW, AXIS_ROLL, AXIS_PITCH)
CAM_ROTATION_ORDER_PYR = (AXIS_ROLL, AXIS_YAW, AXIS_PITCH)

valid_rotation_orders = [
    CAM_ROTATION_ORDER_PYR,
    CAM_ROTATION_ORDER_PRY,
    CAM_ROTATION_ORDER_RPY,
    CAM_ROTATION_ORDER_YPR,
    CAM_ROTATION_ORDER_YRP,
    CAM_ROTATION_ORDER_RYP,
]
class CameraHandler:
    default_camera_rendering_shader = None
    make_entity_when_creating_camera=True






class Camera:
    def __init__(self ,starting_settings :StartupSettings |CameraStartupSettings=active_default_settings ,optional_mouse:Mouse =None,specific_output_settings:OutputStartupSettings=None,culling_method=CULLING_NAIVE_FRUSTUM,autoadd_to_main_scene=True,entity=None,parent=None,make_entity=CameraHandler.make_entity_when_creating_camera):
        """display_to_object must be a Moden Model"""
        if isinstance(starting_settings, StartupSettings):
            starting_settings = starting_settings.camera_startup
        elif isinstance(starting_settings, CameraStartupSettings):
            starting_settings = starting_settings
        else:
            raise TypeError("Expected Settings or CameraSettings, got {}".format(type(starting_settings)))
        starting_settings.is_valid()

        self.active=True
        self._renderer = Renderer()

        self.fov_y=starting_settings.field_of_view_y_axis
        self.fov_x = starting_settings.field_of_view_x_axis
        #THE ROTATIONS ARE APPLIED FROM THE END TO THE BEGINNING
        #MEANING THAT THE ROTATION IS REALLY ROLL->YAW->PITCH
        self.rotation_order =CAM_ROTATION_ORDER_PYR

        self.near_plane = starting_settings.near_plane
        self.far_plane = starting_settings.far_plane
        if specific_output_settings is None:
            self.output = Output(starting_settings.startup_output_settings)
        else:
            self.output = Output(specific_output_settings)
        self.perspective_matrix=self.calculate_perspective_matrix(self.fov_y,self.output.resolution_x,self.output.resolution_y,self.near_plane,self.far_plane)

        self._position_global = glm.vec3(0.0)
        self._position_relative = glm.vec3(0.0)
        self._scale_global = glm.vec3(1.0)
        self._scale_relative = glm.vec3(1.0)

        self._orientation = glm.quat()
        # in degrees
        self.yaw_global= 0
        self.pitch_global= 0
        self.roll_global= 0
        self.yaw_relative = 0
        self.pitch_relative = 0
        self.roll_relative = 0
        self.yaw_sensitivity =1
        self.pitch_sensitivity =1
        self.roll_sensitivity =1


        self.yaw_limits = (starting_settings.yaw_limit_down, starting_settings.yaw_limit_up)
        self.pitch_limits = (starting_settings.pitch_limit_down, starting_settings.pitch_limit_up)
        self.roll_limits = (starting_settings.roll_limit_down, starting_settings.roll_limit_up)

        self.roll_clip_instead_of_wrap = False
        self.yaw_clip_instead_of_wrap = False
        self.pitch_clip_instead_of_wrap = False


        self._assigned_mouse =optional_mouse
        if optional_mouse:
            self.set_mouse(self._assigned_mouse)

        self.paused=False
        self.scene = None
        self.clip_matrix=None
        self._update_clip_matrix()

        self.frustum_planes=None

        self._uniform_helper=UniformHelper()
        self._uniform_helper._set_uniforms(["view_matrix","perspective_matrix"],[self.get_view_matrix,self.perspective_matrix])
        self._uniform_helper._set_uniforms("numLights",0)
        if make_entity and entity is None:
            entity=Entity(cameras=self,entity_type=ENTITY_TYPE_CAMERA)
        self._entity = entity
        self._parent = parent
        self._children = []
        self.set_culling_mode(culling_method)



    #Ordering hierarchy: Calculate>Set>Add>Get>Miscellaneous not necessary for the class
    #Below are the methods more or less exclusively pertaining to the camera itself
    def _update_orientation(self ,mouse_x=None ,mouse_y=None ,window_id=None,delta_x=None,delta_y=None):
        self._orientation = glm.quat()
        for vector in self.rotation_order:
            if vector == AXIS_ROLL:
                angle =self.roll_global
            elif vector == AXIS_PITCH:
                angle =self.pitch_global
            elif vector ==  AXIS_YAW:
                angle =self.yaw_global
            else:
                raise Exception (f"{vector} is not in the list of viable axis in the camera module")
            self._orientation *= glm.angleAxis(glm.radians(angle), glm.vec3(*vector))
        self._update_clip_matrix()
    def _update_clip_matrix(self):
        self.clip_matrix=self.perspective_matrix @ self.get_view_matrix()
        self.clip_matrix = np.array(self.clip_matrix)
    def _update_frustum_planes(self):
        planes = {}

        planes['left'] = self.clip_matrix[3, :] + self.clip_matrix[0, :]
        planes['right'] = self.clip_matrix[3, :] - self.clip_matrix[0, :]
        planes['bottom'] = self.clip_matrix[3, :] + self.clip_matrix[1, :]
        planes['top'] = self.clip_matrix[3, :] - self.clip_matrix[1, :]
        planes['near'] = self.clip_matrix[3, :] + self.clip_matrix[2, :]
        planes['far'] = self.clip_matrix[3, :] - self.clip_matrix[2, :]

        # Normalize planes
        for key in planes:
            planes[key] = self.normalize_plane(planes[key])
        self.frustum_planes=planes
        return self.frustum_planes
    def _handle_rotation_standardization(self ,rotation ,identifier):
        if identifier == 0:
            if self.pitch_clip_instead_of_wrap:
                return self.clip_between(rotation ,self.pitch_limits)
            else:
                return self.wrap_between(rotation ,self.pitch_limits)
        elif identifier == 1:
            if self.yaw_clip_instead_of_wrap:
                return self.clip_between(rotation ,self.yaw_limits)
            else:
                return self.wrap_between(rotation ,self.yaw_limits)
        elif identifier == 2:
            if self.roll_clip_instead_of_wrap:
                return self.clip_between(rotation ,self.roll_limits)
            else:
                return self.wrap_between(rotation ,self.roll_limits)
    def _update_pespective_matrix(self):
        self.perspective_matrix= self.calculate_perspective_matrix(self.fov_y,self.output.resolution_x,self.output.resolution_y,self.near_plane,self.far_plane,self.fov_x)
        self._uniform_helper._set_uniforms(["perspective_matrix"],
                                           [self.perspective_matrix])
    def _update_view_matrix(self):
        self._uniform_helper._set_uniforms(["view_matrix"],
                                           [self.get_view_matrix])
    def calculate_perspective_matrix(self,fov_y:int|str|float=USE_OWN,resolution_x:int|str=USE_OWN,resolution_y:int|str=USE_OWN,near_plane:int|float=USE_OWN,far_plane:int|float=USE_OWN,fov_x:int|str|float=USE_OWN):
        """
        The function , upon being called, calculates the camera´s perspective matrix (but does not set it)
        This does NOT update any value. it simply computes a matrix based on the data it is given.
        Updates to things like FOV or resolution should be done in camera and its output, respectively

        Computes the missing FOV if only one of the 2 axis is provided
        (fov_y or fov_x accept RECOMPUTE or "recompute" as their value, such that the missing axis is calculated
        based on aspect ratio and the present axis.)
        (Can give unfair advantages if fov_x is recalculated automatically, as some may stretch their window very wide)

        Overrides the automatic math of OpenGL.GLM´s matrix maker to use both FOVs if they are both provided
        (Can lead to heavy stretching of the image depending on if the user decided to override)

        Automatically makes the camera be recognized as a "Reverse Z Buffer" camera if
        the near plane(render distance minimum) is bigger than the far plane (maximum)
        (Offers little to no texture Z fighting at long distances, unlike normal cameras)
        (can be a little buggy with normal post-processing shaders, because the shader math for normal Z Buffer
        and Reverse Z buffer cameras is different, so custom shaders are needed.)


        """
        aspect=resolution_x/resolution_y
        if fov_y==USE_OWN:
            fov_y=self.fov_y
        elif fov_y==RECOMPUTE:
            if fov_x!=RECOMPUTE:
                actual_fov_x = self.fov_x if fov_x == USE_OWN else fov_x
                half_fov_x_rad = glm.radians(actual_fov_x / 2.0)
                fov_y = 2.0 * glm.degrees(glm.atan(glm.tan(half_fov_x_rad) / aspect))
            else:
                raise ValueError("fov_y and fov_x cannot both be RECOMPUTE when asking for a recalculation of the perspective matrix.\n Please change the values of at least one or both to USE_OWN or numbers.")
        if fov_x==USE_OWN:
            fov_x=self.fov_x
        elif fov_x == RECOMPUTE:
            fov_x=None
        if resolution_x==USE_OWN:
            resolution_x=self.output.resolution_x
        if resolution_y==USE_OWN:
            resolution_y=self.output.resolution_y
        if near_plane == USE_OWN:
            near_plane = self.near_plane
        if far_plane == USE_OWN:
            far_plane = self.far_plane
        perspective_matrix=self.output._calculate_perspective_matrix(fov_y,resolution_x,resolution_y,near_plane,far_plane,fov_x)
        return perspective_matrix
    def normalize_plane(self,plane):
        norm = np.linalg.norm(plane[:3])
        return plane / norm
    # def entity_in_view(self, entity):
    #     c = entity.get_position()
    #     cx, cy, cz = c[0],c[1],c[2]
    #     radius = entity.get_bounding_radius()
    #     planes = self.frustum_planes.values()
    #     for plane in planes:
    #         distance = (plane[0] * cx + plane[1] * cy + plane[2] * cz) + plane[3]
    #
    #         if distance < -radius:
    #             return False
    #     return True

    def set_position(self, x=USE_OWN, y=USE_OWN, z=USE_OWN, relative_to_self=True):
        if relative_to_self:
            px, py, pz = 0, 0, 0
        else:
            px, py, pz = self.get_parent().get_position()
        if x != USE_OWN:
            self._position_relative.x = x
            self._position_global.x = x + px
        if y != USE_OWN:
            self._position_relative.y = y
            self._position_global.y = y + py
        if z != USE_OWN:
            self._position_relative.z = z
            self._position_global.z = z + pz
        self._update_clip_matrix()
    def set_rotation(self, yaw=USE_OWN, pitch=USE_OWN, roll=USE_OWN, relative_to_self=True):  # TODO maybe add quats for rotation
        if relative_to_self:
            pp, py, pr = 0, 0, 0
        else:
            pp, py, pr = self.get_parent().get_rotation()
        if pitch != USE_OWN:
            self.pitch_relative = pitch
            self.pitch_global = pitch + pp
        if yaw != USE_OWN:
            self.yaw_relative = yaw
            self.yaw_global = yaw + py
        if roll != USE_OWN:
            self.roll_relative = roll
            self.roll_global = roll + pr
        self._update_orientation()
        self._update_clip_matrix()
    def change_position(self, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
        if relative_to == USE_OWN:
            target = self.get_parent()
        else:
            target = relative_to
        origin = target.get_position()
        if change_vectorially:
            rot_context = target.get_rotation_matrix()
            offset = glm.vec3(x, y, z)
            direction = glm.vec3(rot_context * glm.vec4(offset, 0.0))
            new_pos = origin + direction
        else:
            new_pos = origin + glm.vec3(x, y, z)

        self.set_position(new_pos.x, new_pos.y, new_pos.z)
    def change_rotation(self, yaw=0, pitch=0, roll=0, relative_to=USE_OWN):
        if relative_to == USE_OWN:
            relative_to = self.get_parent()
        target = relative_to.get_rotation()
        self.set_rotation(target[0] + yaw, target[1] + pitch, target[2] + roll)




    def set_culling_mode(self,culling_mode=USE_OWN):
        if culling_mode == USE_OWN:
            culling_mode=CULLING_NAIVE_FRUSTUM
        self._renderer._set_culling_mode(culling_mode)
    def change_fov(self,fov_x=USE_OWN,fov_y=USE_OWN,update_matrix=True):
        if fov_x == USE_OWN:
            fov_x = self.fov_x
        if fov_y == USE_OWN:
            fov_y = self.fov_y
        self.fov_x+=fov_x
        self.fov_y+=fov_y
        if update_matrix:
            self._update_pespective_matrix()
    def set_fov(self,fov_x=USE_OWN,fov_y=USE_OWN,update_matrix=True):
        if fov_x == USE_OWN:
            fov_x = self.fov_x
        if fov_y == USE_OWN:
            fov_y = self.fov_y
        self.fov_x=fov_x
        self.fov_y=fov_y
        if update_matrix:
            self._update_pespective_matrix()
        self._update_clip_matrix()
    def set_scene(self,scene):
        self.scene=scene

    def add_children(self,children):
        if not isinstance(children,list):
            children=[children]
        self._children.extend(children)
    def set_parent(self,new_parent):
        self.orphan_self()
        self._parent=new_parent
        self._parent.add_children(self)
    def get_parent(self):
        return self._parent if self._parent is not None else self
    def orphan_self(self):
        if self._parent:
            self._parent.orphan_children(self)
    def orphan_children(self,children):
        if not isinstance(children,list):
            children=[children]
        for child in children:
            self._children.remove(child)


    def model_in_view(self, model):
        """
        Robust Axis Aligned Bounding Box vs Frustum test.
        Fixed typos and optimized by removing redundant array allocations.
        """
        c = model.get_position()
        cx, cy, cz = c[0], c[1], c[2]
        radius = model.get_bounding_radius()
        planes = self.frustum_planes.values()
        for plane in planes:
            distance = (plane[0] * cx + plane[1] * cy + plane[2] * cz) + plane[3]

            if distance < -radius:
                return False
        return True

    def light_in_view(self, light):
        if light.type == 2:  # Global Directional
            return True

        # Sphere vs frustum logic
        centre_world = np.array(light.get_position(), dtype=float)
        radius = light.radius

        for plane in self.frustum_planes.values():
            distance = np.dot(plane[:3], centre_world) + plane[3]
            if distance < -radius:
                return False
        return True
    def get_position(self):
        return self._position_global
    def get_view_matrix(self):
        pos=self.get_position()
        return glm.lookAt(pos, pos + self.get_front_direction(False), self.get_up_direction(False))
    def get_perspective_matrix(self):
        return self.perspective_matrix
    def get_rotation(self):
        return glm.vec3(self.yaw_global, self.pitch_global, self.roll_global)
    def get_rotation_matrix(self):
        """Converts the orientation quaternion into a 4x4 matrix."""
        return glm.mat4_cast(self._orientation)
    def get_front_direction(self ,use_only_pitch=False):

        if use_only_pitch:
            pitch_quat = glm.angleAxis(glm.radians(self.pitch_global), glm.vec3(AXIS_PITCH))
            front = pitch_quat * glm.vec3(0.0, 0.0, -1.0)
        else:
            front = self._orientation * glm.vec3(0.0, 0.0, -1.0)

        return glm.normalize(front)
    def get_right_direction(self, use_only_pitch=False):
        if use_only_pitch:
            pitch_quat = glm.angleAxis(glm.radians(self.pitch_global), glm.vec3(AXIS_PITCH))
            right = pitch_quat * glm.vec3(-1.0, 0.0, 0.0)
        else:
            right = self._orientation * glm.vec3(-1.0, 0.0, 0.0)

        return glm.normalize(right)
    def get_up_direction(self, use_only_pitch=False):
        if use_only_pitch:
            up = glm.vec3(AXIS_YAW)
        else:
            up = self._orientation * glm.vec3(0.0, 1.0, 0.0)

        return glm.normalize(up)

    def get_entity(self):
        return self._entity



    def set_mouse(self ,mouse :Mouse ,autoset_basic_camera_rotation_to_mouse=True,autoset_roll_camera_rotation_to_mouse=KEY_V):
        self._assigned_mouse =mouse

        mouse.add_action_to_layouts(self._update_orientation ,None ,MOUSE_MOVE)
        if autoset_basic_camera_rotation_to_mouse:
            self.autoset_mouse_as_pitch_and_yaw(self._assigned_mouse)
        if autoset_roll_camera_rotation_to_mouse is not False and autoset_roll_camera_rotation_to_mouse is not None:
            self.autoset_mouse_roll_on_key(mouse ,USE_OWN ,autoset_roll_camera_rotation_to_mouse)
    def autoset_mouse_as_pitch_and_yaw(self ,mouse :Mouse,mouse_layout:MouseLayout =USE_OWN):
        if mouse_layout == USE_OWN:
            mouse_layout =mouse.active_layout
        mouse.add_action_to_layouts(self._basic_orientation_mouse_to_camera_processor,None,action_type=MOUSE_MOVE,layouts=mouse_layout)
    def autoset_mouse_roll_on_key(self ,mouse:Mouse,mouse_layout:MouseLayout|str =USE_OWN ,which_key=KEY_V):
        if mouse_layout == USE_OWN:
            mouse_layout =mouse.active_layout
        mouse.add_action_to_layouts(self._roll_orientation_mouse_to_camera_processor, None, MOUSE_MOVE ,which_key,layouts=mouse_layout)
    def _basic_orientation_mouse_to_camera_processor(self ,mouse_x ,mouse_y ,window_id,inverted=True,delta_x=None,delta_y=None): #TODO add inverted
        # TODO maybe handle rotations and standardization better
        # offset_x ,offset_y =delta_x,delta_y
        # self.yaw_global-=offset_x * self.yaw_sensitivity
        # self.pitch_global -= offset_y * self.pitch_sensitivity
        # self.yaw_global= self._handle_rotation_standardization(self.yaw_global,1)
        # self.pitch_global= self._handle_rotation_standardization(self.pitch_global,0)
        self.change_rotation(-delta_x*self.yaw_sensitivity,-delta_y*self.pitch_sensitivity)
        self._update_orientation()

    def _roll_orientation_mouse_to_camera_processor(self ,mouse_x ,mouse_y ,window_id):
        offset_x =self._assigned_mouse.get_delta_distance(mouse_x ,mouse_y)[0]
        # TODO maybe handle rotations and standardization better
        self.roll_global+=offset_x *self.roll_sensitivity
        self.roll_global= self._handle_rotation_standardization(self.roll_global,2)
        self.yaw_global+= offset_x * self.yaw_sensitivity
        self.yaw_global= self._handle_rotation_standardization(self.yaw_global,1)
        self._update_orientation()
    @staticmethod
    def wrap_between(what_to_wrap: int | float, min_value: int | float | tuple,max_value: int | float = None) -> int | float:
        if isinstance(min_value, tuple):
            max_value = min_value[1]
            min_value = min_value[0]
        return (what_to_wrap - min_value) % (max_value - min_value) + min_value
    @staticmethod
    def clip_between(what_to_clip: int | float, min_value: int | float | tuple,max_value: int | float = None) -> int | float:
        if isinstance(min_value, tuple):
            max_value = min_value[1]
            min_value = min_value[0]
        return max(min_value, min(what_to_clip, max_value))

    #Below are the methods pertaining to the uniform helper
    def update_view_and_perspective(self):
        self._update_pespective_matrix()
        self._update_view_matrix()

    def set_uniforms(self,names,values,struct=None):
        self._uniform_helper._set_uniforms(names,values,struct)
    def get_all_uniform_names(self):
        return self._uniform_helper._get_all_uniform_names()
    def get_uniforms(self,names):
        return self._uniform_helper._get_uniforms(names)
    #Below are the methods pertaining to the renderer

    def set_main_shader(self,shaders:CompleteShader|list):
        """Shaders must be a CompleteShader or a list"""
        self._renderer._add_shader(shaders,PASS_MAIN)
    def set_order_of_shader(self,shader:CompleteShader,new_index:int,swap_instead_of_move:bool=False):
        self._renderer._reorder_shaders(shader,new_index,swap_instead_of_move)
    def add_shaders(self,shaders:CompleteShader|list,type_of_pass):
        """Shaders must be a CompleteShader or a list"""
        self._renderer._add_shader(shaders,type_of_pass)
    def add_models_to_shaders(self,shaders:CompleteShader|list,models:Model|list):
        self._renderer._add_models_to_shader(shaders, models)
    def add_layers_to_shaders(self,shaders:CompleteShader|list,layers):
        """Restricts a text or UI shader to specific layers, the way models are assigned
           to shaders. A shader with no layers attached draws every layer of its kind,
           which is fine until a camera has both world-space text and screen-space UI
           text: then each shader would draw the other's layers in the wrong projection."""
        self._renderer._add_layers_to_shader(shaders, layers)

    def get_fov(self):
        return self.fov_x,self.fov_y

    def render(self,render_to_output:bool=True):
        self.output._activate_output(render_to_output)
        self._update_frustum_planes()
        # The frustum planes must be current before culling, since
        # naive_sphere_frustum_culling() reads camera.frustum_planes.
        visible_in_view = self._renderer.culling_method(self)
        active_lights_in_view = [renderable for renderable in visible_in_view if isinstance(renderable, Light)]
        num_lights = LightHandler._update_gpu_data(active_lights_in_view)
        self._uniform_helper._set_uniforms(["numLights"], [num_lights])
        # The renderer would otherwise repeat the frustum test we just did, so hand it
        # the result we already have.
        self._renderer._render(self, visible_in_view)








class Output:
    #  Make sure that the window rendering loop plays nicely with these buffers, and make it identify what the framebuffer has , so as to clear it (GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | stencil)
    def __init__(self,starting_settings:OutputStartupSettings):
        self.resolution_x=starting_settings.resolution_x
        self.resolution_y=starting_settings.resolution_y
        self.frame_buffer_object = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.frame_buffer_object)
        # self.texture is the slot integer (not a raw GL id/handle): "engine testing.py"
        # feeds it straight into mesh vertex data as a texture index, so it must stay
        # the slot the bound-texture-unit scheme uses. self._texture_id is the raw GL
        # texture id, kept around only because glFramebufferTexture2D needs it below.
        # There is no more bindless "handle"/residency concept, so that attribute is gone.
        self.texture, self._texture_id = TextureHandler.create_render_target_texture(
            self.frame_buffer_object, self.resolution_x, self.resolution_y
        )
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._texture_id, 0)
        self.render_buffer_object=glGenRenderbuffers(1)
        if starting_settings.add_stencil_buffer and starting_settings.add_depth_buffer:
            self.buffer_clear_tags=GL_COLOR_BUFFER_BIT |GL_DEPTH_BUFFER_BIT|GL_STENCIL_BUFFER_BIT
            glBindRenderbuffer(GL_RENDERBUFFER, self.render_buffer_object)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, self.resolution_x, self.resolution_y)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER,self.render_buffer_object)
            glBindRenderbuffer(GL_RENDERBUFFER, 0)
        elif starting_settings.add_depth_buffer:
            self.buffer_clear_tags = GL_COLOR_BUFFER_BIT  | GL_DEPTH_BUFFER_BIT
            glBindRenderbuffer(GL_RENDERBUFFER, self.render_buffer_object)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24 , self.resolution_x, self.resolution_y)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER,self.render_buffer_object)
            glBindRenderbuffer(GL_RENDERBUFFER, 0)
        elif starting_settings.add_stencil_buffer:
            self.buffer_clear_tags = GL_COLOR_BUFFER_BIT  | GL_STENCIL_BUFFER_BIT
            glBindRenderbuffer(GL_RENDERBUFFER, self.render_buffer_object)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_STENCIL_INDEX8, self.resolution_x, self.resolution_y)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_STENCIL_ATTACHMENT, GL_RENDERBUFFER,self.render_buffer_object)
            glBindRenderbuffer(GL_RENDERBUFFER, 0)
        else:
            glDeleteRenderbuffers(1, [self.render_buffer_object])
            self.render_buffer_object = None
            self.buffer_clear_tags = GL_COLOR_BUFFER_BIT
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            raise RuntimeError(
                f"Camera output framebuffer (resolution {self.resolution_x}x{self.resolution_y}) "
                f"is incomplete: glCheckFramebufferStatus returned {status!r}."
            )
        glBindFramebuffer(GL_FRAMEBUFFER,0)
    def _calculate_perspective_matrix(self,fov_y,resolution_x,resolution_y,near_plane,far_plane,fov_x):
        resolution_aspect=resolution_x/resolution_y
        if near_plane<far_plane:
            perspective_matrix = glm.perspective(glm.radians(fov_y), resolution_aspect, near_plane, far_plane)
        else:
            perspective_matrix = glm.perspectiveLH_ZO(glm.radians(fov_y), resolution_aspect, near_plane, far_plane)
        if fov_x != RECOMPUTE and fov_x is not None:
            sx = 1.0 / glm.tan(glm.radians(fov_x) / 2.0)
            perspective_matrix[0][0] = sx
        return perspective_matrix
        #TODO
        # Finish framebuffer setup and everything
        # Finish reverse z buffer cameras
        #
        # glDeleteFramebuffers(1,self.frame_buffer_object)
    def _activate_output(self,render_to_output:bool):
        if render_to_output:
            glViewport(0, 0, self.resolution_x,self.resolution_y)
            glBindFramebuffer(GL_FRAMEBUFFER, self.frame_buffer_object)
            glClear(self.buffer_clear_tags)

        else:
            glViewport(0, 0, self.resolution_x, self.resolution_y)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glClear(self.buffer_clear_tags)