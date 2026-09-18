from OpenGL.GL import *
import numpy as np
from pyglm import glm
from dataclasses import dataclass,field
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import USE_OWN,Entity,ENTITY_TYPE_LIGHT
import math
#TODO ADD CLUSTERED SHADING OPTION FOR LIGHTING. WILL BE VERY GOOD
class LightHandler:
    initialized=False
    lights = []
    light_shader_storage_buffer=0
    _gpu_capacity = 10
    make_entity_when_creating_light=True
    @staticmethod
    def _load_light_handler():
        if not LightHandler.initialized:
            LightHandler.light_shader_storage_buffer = glGenBuffers(1)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, LightHandler.light_shader_storage_buffer)
            glBufferData(GL_SHADER_STORAGE_BUFFER, 112 * 10, None, GL_DYNAMIC_DRAW)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, LightHandler.light_shader_storage_buffer)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    @staticmethod
    def _update_gpu_data(visible_lights):
        num_visible = len(visible_lights)
        if num_visible > 0:
            packed_data = LightHandler._pack_lights(visible_lights, num_visible)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, LightHandler.light_shader_storage_buffer)
            if num_visible > LightHandler._gpu_capacity:
                LightHandler._gpu_capacity = num_visible * 2
                glBufferData(GL_SHADER_STORAGE_BUFFER, 112 * LightHandler._gpu_capacity, None, GL_DYNAMIC_DRAW)
            glBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, packed_data.nbytes, packed_data)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

        return num_visible
    @staticmethod
    def _pack_lights(lights_list,number_of_lights):   #TODO optimize because this is allegedly slow to do every frame per camera
        """Internal helper to convert Light objects to a NumPy array."""
        data = np.zeros((number_of_lights, 7, 4), dtype=np.float32)
        for i, l in enumerate(lights_list):
            data[i, 0] = [*l._position, 1.0 if l.on else 0.0]
            data[i, 1] = [*l._direction, float(l.type)]
            data[i, 2] = [l.constant, l.linear, l.quadratic, l.radius]
            data[i, 3] = [l.cutOff, l.outerCutOff, 0.0, 0.0]
            data[i, 4] = [*l.ambient, 0.0]
            data[i, 5] = [*l.diffuse, 0.0]
            data[i, 6] = [*l.specular, 0.0]

        return data.ravel()
@dataclass
class Light:#TODO HAVE LIGHTS BE PER SCENE NOT GLOBAL

    # 0: Point, 1: Spotlight, 2: Global Direction
    __slots__ = [
        "type",
        "_position",
        "_direction",
        "ambient",
        "diffuse",
        "specular",
        "constant",
        "linear",
        "quadratic",
        "cutOff",
        "outerCutOff",
        "radius",
        "on",
        "_entity"
    ]
    def __init__(
        self,
        type: int,
        _position: glm.vec3 = glm.vec3(0.0, 0.0, 0.0),
        _direction: glm.vec3 = glm.vec3(0.0, -1.0, 0.0),
        ambient: list = [0.1, 0.1, 0.1],
        diffuse: list = [1.0, 1.0, 1.0],
        specular: list = [0.5, 0.5, 0.5],
        constant: float = 1.0,
        linear: float = 0.09,
        quadratic: float = 0.032,
        # These should be passed as COSINES for the shader (0.0 to 1.0),
        cutOff: float = 0.97,  # ~14 degrees
        outerCutOff: float = 0.95,  # ~18 degrees
        radius: float = 10.0,
        on: bool = True,
        entity=None,
        make_entity=LightHandler.make_entity_when_creating_light):
        self.type = type
        self._position = _position
        self._direction = _direction
        self.ambient = ambient
        self.diffuse = diffuse
        self.specular = specular
        self.constant = constant
        self.linear = linear
        self.quadratic = quadratic
        self.cutOff = cutOff
        self.outerCutOff = outerCutOff
        self.radius = radius
        self.on = on
        self.calculate_light_radius()

        LightHandler.lights.append(self)
        if make_entity and entity is None:
            entity=Entity(lights=self,entity_type=ENTITY_TYPE_LIGHT)
        self._entity = entity
    def set_parent_entity(self,new_parent_entity):
        #TODO remove from old one add to new one
        pass
    def get_entity(self):
        return self._entity
    def set_spotlight_angles(self, start_fading_angle: float, stop_fading_angle: float):
        """Helper to let users use degrees instead of confusing cosines."""
        self.cutOff = np.cos(np.radians(start_fading_angle))
        self.outerCutOff = np.cos(np.radians(stop_fading_angle))
    def set_simple_radius(self, new_radius: float):
        if self.type == 2: return
        self.radius = new_radius
        self.constant = 1.0
        self.linear = 4.5 / new_radius
        self.quadratic = 75.0 / (new_radius ** 2)
    def calculate_light_radius(self):
        if self.type == 2:
            self.radius = float('inf')
            return self.radius

        threshold = 0.01
        a = self.quadratic
        b = self.linear
        c = self.constant - (1.0 / threshold)

        # Handle cases where quadratic/linear might be 0 (avoid div by zero)
        if a == 0 and b == 0:
            print(f"SOMETHING IS SERIOUSLY WRONG WITH THE RADIUS CALCULATION OF LIGHT {self}\n BOTH QUADRATIC AND LINEAR FLOATS ARE 0")
            self.radius = 10.0
            return self.radius
        discriminant = b ** 2 - 4 * a * c
        if discriminant <= 0:
            print(f"SOMETHING IS SERIOUSLY WRONG WITH THE RADIUS CALCULATION OF LIGHT {self}\nRADIUS CALCULATION FAILED")
            self.radius = 10.0
        else:
            self.radius = (-b + np.sqrt(discriminant)) / (2 * a)
        return self.radius
    def get_position(self):
        return self._position

    def get_rotation(self):
        """This gets the direction/rotation of a light in degrees"""
        x, y, z = self._direction
        pitch = math.degrees(math.asin(y))
        yaw = math.degrees(math.atan2(x, z))
        roll = 0.0  # Direction vectors don't have roll
        return glm.vec3(yaw, pitch, roll)

    def set_position(self, x=USE_OWN, y=USE_OWN, z=USE_OWN):
        if x != USE_OWN: self._position[0] = x
        if y != USE_OWN: self._position[1] = y
        if z != USE_OWN: self._position[2] = z

    def get_rotation_matrix(self):
        # If it's a point light with no specific direction, return identity
        if self.type == 0:
            return glm.mat4(1.0)
        # Use lookAt to create a matrix looking from origin (0,0,0)
        # towards the direction vector.
        # We use (0,1,0) as a stable 'up' vector.
        return glm.inverse(glm.lookAt(glm.vec3(0.0), self._direction, glm.vec3(0, 1, 0)))


    def set_rotation(self, yaw=USE_OWN, pitch=USE_OWN, roll=USE_OWN):
        import math
        cur_yaw, cur_pitch, _ = self.get_rotation()
        y_deg = yaw if yaw != USE_OWN else cur_yaw
        p_deg = pitch if pitch != USE_OWN else cur_pitch

        rad_y = math.radians(y_deg)
        rad_p = math.radians(p_deg)

        # Calculate new direction vector
        self._direction[0] = math.cos(rad_p) * math.sin(rad_y)
        self._direction[1] = math.sin(-rad_p)
        self._direction[2] = math.cos(rad_p) * math.cos(rad_y)

    def change_position(self, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
        if relative_to == USE_OWN:
            target = self
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
        rel = relative_to.get_rotation() if relative_to != USE_OWN else self.get_rotation()
        self.set_rotation(rel[0] + yaw, rel[1] + pitch, rel[2] + roll)