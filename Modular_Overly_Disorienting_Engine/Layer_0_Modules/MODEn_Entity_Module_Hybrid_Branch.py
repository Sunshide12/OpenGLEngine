from Modular_Overly_Disorienting_Engine.Layer_0_Modules import USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Physics_Body_Physics_Branch import PhysicsBody,BEHAVIOUR_STATIC

ENTITY_TYPE_MIXED="entitymixed"
ENTITY_TYPE_CAMERA="entitycamera"
ENTITY_TYPE_MODEL="entitymodel"
ENTITY_TYPE_LIGHT="entitylight"


class EntityHandler:
    skip_type_checking=False
class Entity:
    def __init__(self,models=None,physics_bodies=None,cameras=None,lights=None,entity_type=USE_OWN):
        if not isinstance(models, list):
            models = [] if models is None else [models]
        if not isinstance(physics_bodies, list):
            physics_bodies = [PhysicsBody(BEHAVIOUR_STATIC)] if physics_bodies is None else [physics_bodies]
        if not isinstance(cameras, list):
            cameras = [] if cameras is None else [cameras]
        if not isinstance(lights, list):
            lights = [] if lights is None else [lights]

        self._models = models
        self._physics_bodies = physics_bodies
        self._cameras = cameras
        self._lights = lights
        if entity_type== USE_OWN:
            self._entity_type=self.calculate_entity_type()
        else:
            self._entity_type=entity_type

    def calculate_entity_type(self):
        entity_type=None
        nonechecker = 0
        for counter, component_list in enumerate([self._models, self._lights, self._cameras]):
            if component_list == [] :
                nonechecker += 1
            elif entity_type is None:
                entity_type = counter
        if nonechecker == 3:
            raise Exception("Cannot have an empty entity. Maybe crashing is a bit harsh")
        elif nonechecker != 2:
            entity_type = ENTITY_TYPE_MIXED
        else:
            if entity_type == 0:
                entity_type = ENTITY_TYPE_MODEL
            elif entity_type == 1:
                entity_type = ENTITY_TYPE_LIGHT
            elif entity_type == 2:
                entity_type = ENTITY_TYPE_CAMERA
        return entity_type
    def set_entity_type(self,label):
        self._type=label
    def get_physics_body_type(self,body_index=0):
        return self._physics_bodies[body_index].get_behaviour()
    def get_render_branch_component_lists(self):
        return [self._models,self._cameras,self._lights]
    def get_camera_list(self):
        return self._cameras
    def add_models(self,models):
        self._models.extend(models)