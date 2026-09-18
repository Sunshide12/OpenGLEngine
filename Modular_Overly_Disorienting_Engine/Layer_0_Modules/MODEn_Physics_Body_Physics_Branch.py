
BEHAVIOUR_STATIC="behaviourstatic"
BEHAVIOUR_DYNAMIC="behaviourdynamic"
BEHAVIOUR_HYBRID="behaviourhybrid"
BEHAVIOUR_NONE="behaviournone"
class PhysicsBody:
    def __init__(self,behaviour:str=BEHAVIOUR_STATIC):
        self._behaviour=behaviour
    def get_behaviour(self):
        return self._behaviour