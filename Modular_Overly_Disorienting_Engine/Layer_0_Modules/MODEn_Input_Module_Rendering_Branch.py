from typing import Union


from glfw import *
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Settings_Module_Rendering_Branch import purpose_text,USE_OWN
purpose_text("Handles the acquisition of input and linking actions to said input")
MOUSE_MOVE="move"
MOUSE_SCROLL="scroll"
MOUSE_ENTER_WINDOW="entered window"
MOUSE_EXIT_WINDOW="exited window"
KEY_REGARDLESS=-1
KEY_ANY_MONITORED=-2
KEY_NONE=-3
KEY_ANY_CONTROL=MOD_CONTROL
KEY_ANY_SHIFT=MOD_SHIFT
KEY_ANY_ALT=MOD_ALT
ALL_POSSIBLE="all"
HOLD="hold"
HOLD_WITH_DELAY=REPEAT
valid_action_types=[PRESS,RELEASE,HOLD,HOLD_WITH_DELAY,REPEAT,MOUSE_MOVE,MOUSE_SCROLL,MOUSE_ENTER_WINDOW,MOUSE_EXIT_WINDOW]
special_keys=[KEY_REGARDLESS,KEY_ANY_MONITORED,KEY_NONE]
USE_LAYOUT="layout"


class KeyboardLayout:
    def __init__(self):
        self._action_dictionary = {}
        self._monitored_keys = set()
        self._held_actions = set()  # Standardized collection for continuous input
        self.treat_multiple_keys_as_multiple_actions = True

    def add_action(self, function_reference: callable, key=KEY_SPACE, action_type=PRESS,
                   modifiers: frozenset | set | int | list= KEY_REGARDLESS):
        """Standardized: Adds an action to this layout's data structure."""
        # Standardize modifiers to frozenset for hashing
        if isinstance(modifiers, (set, list)):
            mod_set = frozenset(modifiers).union({KEY_REGARDLESS, KEY_ANY_MONITORED})
        elif isinstance(modifiers, int):
            mod_set = frozenset([modifiers]).union({KEY_REGARDLESS, KEY_ANY_MONITORED})
        else:
            mod_set = modifiers

        if mod_set not in self._monitored_keys and mod_set not in special_keys:
            self._monitored_keys.add(mod_set)

        # Build lookup tree: Key -> Action -> Modifiers -> [Callbacks]
        if key not in self._action_dictionary:
            self._action_dictionary[key] = {}
        if action_type not in self._action_dictionary[key]:
            self._action_dictionary[key][action_type] = {}

        if mod_set not in self._action_dictionary[key][action_type]:
            self._action_dictionary[key][action_type][mod_set] = []

        self._action_dictionary[key][action_type][mod_set].append(function_reference)

    def get_held_actions(self):
        """Standardized: Returns the group of actions currently being held."""
        return self._held_actions

    def _callback_function(self, window_id, key, scancode, action, built_in_mods):
        active_mods = _resolve_active_modifiers(self, window_id)

        # 1. Handle Standard Actions (PRESS, RELEASE, REPEAT)
        actions = self._action_dictionary.get(key, {}).get(action, {}).get(active_mods)
        if actions:
            for func in actions:
                func()

        # 2. Handle HOLD Logic
        # If the key is pressed, add its 'HOLD' variant functions to the held set
        if action == PRESS:
            hold_actions = self._action_dictionary.get(key, {}).get(HOLD, {}).get(active_mods)
            if hold_actions:
                for func in hold_actions:
                    self._held_actions.add(func)

        # If released, remove all 'HOLD' variant functions for this key
        elif action == RELEASE:
            # We look up all possible modifiers for this key under the HOLD action to ensure cleanup
            action_configs = self._action_dictionary.get(key, {}).get(HOLD, {})
            for mod_set in action_configs:
                for func in action_configs[mod_set]:
                    self._held_actions.discard(func)


class MouseLayout:
    def __init__(self):
        self._action_dictionary = {}
        self._monitored_keys = set()
        self._held_actions = set() # Standardized collection

        self._last_x=0
        self._last_y=0
    def add_action(self, function_reference: callable, button=MOUSE_BUTTON_LEFT, action_type=PRESS,
                   modifiers: frozenset | set | int | list = KEY_REGARDLESS):
        """Standardized: Adds a mouse action to this layout's data structure."""
        if isinstance(modifiers, (set, list)):
            mod_set = frozenset(modifiers).union({KEY_REGARDLESS, KEY_ANY_MONITORED})
        elif isinstance(modifiers, int):
            mod_set = frozenset([modifiers]).union({KEY_REGARDLESS, KEY_ANY_MONITORED})
        else:
            mod_set = modifiers

        if mod_set not in self._monitored_keys and mod_set not in special_keys:
            self._monitored_keys.add(mod_set)

        if mod_set not in self._monitored_keys:
            self._monitored_keys.add(mod_set)

        if button not in self._action_dictionary:
            self._action_dictionary[button] = {}
        if action_type not in self._action_dictionary[button]:
            self._action_dictionary[button][action_type] = {}

        if mod_set not in self._action_dictionary[button][action_type]:
            self._action_dictionary[button][action_type][mod_set] = []

        self._action_dictionary[button][action_type][mod_set].append(function_reference)



    def get_held_actions(self):
        return self._held_actions

    def _click_function(self, window_id, button, action, mods):
        active_mods = _resolve_active_modifiers(self, window_id)
        actions = self._action_dictionary.get(button, {}).get(action, {}).get(active_mods)
        if actions:
            for func in actions:
                func(mouse_x=self._last_x,mouse_y=self._last_y,window_id=window_id)

        if action == PRESS:
            hold_actions = self._action_dictionary.get(button, {}).get(HOLD, {}).get(active_mods)
            if hold_actions:
                for func in hold_actions:
                    self._held_actions.add(func)
        elif action == RELEASE:
            action_configs = self._action_dictionary.get(button, {}).get(HOLD, {})
            for mod_set in action_configs:
                for func in action_configs[mod_set]:
                    self._held_actions.discard(func)

    def _move_function(self, window_id, x, y):
        active_mods = _resolve_active_modifiers(self, window_id)
        actions = self._action_dictionary.get(None, {}).get(MOUSE_MOVE, {}).get(active_mods)
        dx,dy=x-self._last_x,y-self._last_y
        if actions:
            for func in actions:
                # Note: Added window_id here to match your callback signature
                func(mouse_x=x, mouse_y=y, window_id=window_id,delta_x=dx,delta_y=dy)
        self._last_x, self._last_y = x, y

    def _scroll_function(self, window_id, mouse_x, mouse_y):
        active_mods = _resolve_active_modifiers(self, window_id)
        actions = self._action_dictionary.get(None, {}).get(MOUSE_SCROLL, {}).get(active_mods)
        if actions:
            for func in actions:
                func(mouse_x=mouse_x, mouse_y=mouse_y,window_id=window_id)

    def _enter_function(self, window_id, entered):
        """Standardized: Handles cursor entering or leaving the window area."""
        active_mods = _resolve_active_modifiers(self, window_id)
        event_type = MOUSE_ENTER_WINDOW if entered else MOUSE_EXIT_WINDOW

        actions = self._action_dictionary.get(event_type, {}).get(PRESS, {}).get(active_mods)
        if actions:
            for func in actions:
                func()


class Keyboard:
    def __init__(self, active_layout: KeyboardLayout):
        self.layouts = []
        if active_layout is not None:
            self.active_layout = active_layout
            self.add_layouts(self.active_layout)
            self.set_active_layout(self.active_layout)
        else:
            self.active_layout = None



    def add_layouts(self, layouts: KeyboardLayout):
        if not isinstance(layouts,list):
            layouts=[layouts]
        for layout in layouts:
            if layout not in self.layouts:
                self.layouts.append(layout)
    def add_action_to_layouts(self,function_reference:callable,key=KEY_SPACE,action_type=PRESS,modifiers: frozenset | set | int | list=KEY_REGARDLESS,layouts:KeyboardLayout|list=USE_OWN):
        if layouts == USE_OWN:
            layouts=[self.active_layout]
        if not isinstance(layouts,list):
            layouts=[layouts]
        for layout in layouts:
            layout.add_action(function_reference, key, action_type,modifiers)
    def set_active_layout(self, layout: KeyboardLayout):
        if layout in self.layouts:
            self.active_layout = layout

    def get_active_layout(self) -> KeyboardLayout:
        return self.active_layout

class Mouse:
    def __init__(self, active_layout: MouseLayout):
        self.layouts = []
        if active_layout is not None:
            self.active_layout = active_layout
            self.add_layouts(self.active_layout)
            self.set_active_layout(self.active_layout)
        else:
            self.active_layout=None
        self._last_x, self._last_y = 0, 0

    def get_delta_distance(self, current_x, current_y):
        dx, dy = current_x - self._last_x, current_y - self._last_y
        self._last_x, self._last_y = current_x, current_y
        return dx , dy
    def add_layouts(self, layouts: MouseLayout):
        if not isinstance(layouts, list):
            layouts = [layouts]
        for layout in layouts:
            if layout not in self.layouts:
                self.layouts.append(layout)
    def add_action_to_layouts(self,function_reference:callable,button=MOUSE_BUTTON_LEFT,action_type=PRESS,modifiers: frozenset | set | int | list=KEY_REGARDLESS,layouts:KeyboardLayout|list=USE_OWN):
        if layouts == USE_OWN:
            layouts=[self.active_layout]
        if not isinstance(layouts,list):
            layouts=[layouts]
        for layout in layouts:
            layout.add_action(function_reference, button, action_type,modifiers)
    def set_active_layout(self, layout: MouseLayout):
        if layout in self.layouts:
            self.active_layout = layout
    def get_active_layout(self) -> MouseLayout:
        return self.active_layout
def _resolve_active_modifiers(layout, window_id):
    """Determines which modifier set is currently physically pressed on the window."""
    for mod_group in sorted(layout._monitored_keys, key=len, reverse=True):
        if isinstance(mod_group, frozenset):
            # Check if every key in this registered group is pressed
            if all(get_key(window_id, k) == PRESS for k in mod_group if k > 0):
                return mod_group

        # If no registered groups match, return the default
    return KEY_REGARDLESS