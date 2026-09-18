# TODO
#  Add a way to create textures as dynamic load instead of always static_draw (additional note for clarity below)
import os
from OpenGL.GL import *
from PIL import Image as pilimage
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import USE_OWN
import numpy as np

# How many texture units a single draw call is allowed to see at once.
# 16 is the minimum that the OpenGL spec guarantees for GL_MAX_TEXTURE_IMAGE_UNITS,
# so building the shaders around it keeps them compiling on every driver.
# The engine can still own far more textures than this, because slots are mapped
# onto units at draw time (see TextureHandler.ensure_resident).
TEXTURE_UNIT_COUNT = 16

_UNBOUND = -1


class TextureHandler:
    """
       The coordinate system for it is S T R instead of X Y Z
       For GL_CLAMP_TO_BORDER we also need to specify a 4 float list for the bordor color

       GL_TEXTURE_MIN_FILTER and MAX sets the operation for minifying and magnifying textures
       GL_NEAREST (blockier, quicker)
       GL_LINEAR (smoother, more expensive)

       GL_NEAREST_MIPMAP_NEAREST: takes the nearest mipmap to match the pixel size and uses nearest neighbor interpolation for texture sampling.
       GL_LINEAR_MIPMAP_NEAREST: takes the nearest mipmap level and samples that level using linear interpolation.
       GL_NEAREST_MIPMAP_LINEAR: linearly interpolates between the two mipmaps that most closely match the size of a pixel and samples the interpolated level via nearest neighbor interpolation.
       GL_LINEAR_MIPMAP_LINEAR: linearly interpolates between the two closest mipmaps and samples the interpolated level via linear interpolation.

       Textures are handed to the shaders as "slots". A slot is just a stable integer
       that a mesh (or a text character) stores to say "this is my texture".
       Because a draw call can only see TEXTURE_UNIT_COUNT textures at a time, the
       handler keeps a slot -> texture unit table in the SSBO bound at binding 0,
       and the shaders read that table to pick the right sampler.
       A slot whose texture is not currently bound reads back as -1, which the
       shaders draw as magenta so that the mistake is visible instead of silent.
       """
    initialized = False
    name_id_dict = {}  # texture name → tex_id
    name_slot_dict = {}  # texture name → slot
    slot_id_list = []  # slot → tex_id
    slot_unit_list = []  # slot → texture unit, or _UNBOUND
    unit_slot_list = [_UNBOUND] * TEXTURE_UNIT_COUNT  # texture unit → slot, or _UNBOUND
    texture_shader_storage_buffer = 0
    max_texture_units = TEXTURE_UNIT_COUNT
    default_texture_file_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _slot_table_dirty = False
    _use_counter = 0
    _slot_last_used = []  # slot → the value of _use_counter when it was last needed
    _warned_about_thrashing = False

    @staticmethod
    def _load_texture_handler():

        if not TextureHandler.initialized:
            # The driver decides how many samplers a fragment shader may touch. We never
            # use more than TEXTURE_UNIT_COUNT because that is what the shaders declare,
            # but clamping keeps us honest on a driver that reports fewer than the minimum.
            try:
                reported_units = int(glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS))
            except Exception:
                reported_units = TEXTURE_UNIT_COUNT
            TextureHandler.max_texture_units = max(1, min(TEXTURE_UNIT_COUNT, reported_units))
            TextureHandler.unit_slot_list = [_UNBOUND] * TextureHandler.max_texture_units

            TextureHandler.texture_shader_storage_buffer = glGenBuffers(1)
            TextureHandler.get_textures("placeholder.png")
            TextureHandler._update_texture_shader_storage_buffer()
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, TextureHandler.texture_shader_storage_buffer)
            TextureHandler.initialized = True
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    @staticmethod
    def get_textures(image_names: str | list | np.uintc | int, minification_filter=GL_NEAREST_MIPMAP_NEAREST,
                     magnification_filter=GL_NEAREST, wrapping_x_axis=GL_CLAMP_TO_EDGE,
                     wrapping_y_axis=GL_CLAMP_TO_EDGE, file_path: str = USE_OWN, generate_mipmap: bool = True,
                     return_id_with_slot: bool = False):
        """Loads a texture is it wasn't yet loaded
        Returns the slot of an image, which shaders want.
        Can return the OpenGL id alongside it for other purposes if needed."""

        if file_path == USE_OWN:
            file_path = TextureHandler.default_texture_file_path
        if isinstance(image_names, str) or isinstance(image_names, int) or isinstance(image_names, np.uintc):
            if hasattr(image_names, 'item'):
                image_names = image_names.item()
            if image_names in TextureHandler.name_id_dict:
                if not return_id_with_slot:
                    return TextureHandler.name_slot_dict[image_names]
                else:
                    return TextureHandler.name_slot_dict[image_names], TextureHandler.name_id_dict[image_names]
            else:

                slot, tex_id = TextureHandler._generate_texture(image_names, minification_filter, magnification_filter,
                                                                wrapping_x_axis, wrapping_y_axis, file_path,
                                                                generate_mipmap)
                TextureHandler._update_texture_shader_storage_buffer()
                if not return_id_with_slot:
                    return slot
                else:
                    return slot, tex_id
        else:
            made_textures = False
            slots = []
            tex_ids = []
            for name in image_names:
                if name in TextureHandler.name_id_dict:
                    slots.append(TextureHandler.name_slot_dict[name])
                    if return_id_with_slot:
                        tex_ids.append(TextureHandler.name_id_dict[name])

                else:
                    made_textures = True
                    slot, tex_id = TextureHandler._generate_texture(name, minification_filter, magnification_filter,
                                                                    wrapping_x_axis, wrapping_y_axis, file_path,
                                                                    generate_mipmap)
                    slots.append(slot)
                    if return_id_with_slot:
                        tex_ids.append(tex_id)

            if made_textures:
                TextureHandler._update_texture_shader_storage_buffer()
            if return_id_with_slot:
                return slots, tex_ids
            else:
                return slots

    @staticmethod
    def create_render_target_texture(key, width: int, height: int, minification_filter=GL_LINEAR,
                                     magnification_filter=GL_LINEAR, wrapping_x_axis=GL_CLAMP_TO_EDGE,
                                     wrapping_y_axis=GL_CLAMP_TO_EDGE):
        """Makes an empty colour texture meant to be attached to a framebuffer.
           'key' is whatever the caller wants to look the texture up by later
           (a camera's Output passes its framebuffer id).
           Returns the slot and the OpenGL texture id, because whoever attaches it
           to a framebuffer needs the raw id."""
        if key in TextureHandler.name_id_dict:
            return TextureHandler.name_slot_dict[key], TextureHandler.name_id_dict[key]

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, width, height)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, minification_filter)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, magnification_filter)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrapping_x_axis)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrapping_y_axis)
        glBindTexture(GL_TEXTURE_2D, 0)

        slot = TextureHandler._register_texture(key, tex_id)
        TextureHandler._update_texture_shader_storage_buffer()
        return slot, tex_id

    @staticmethod
    def _generate_texture(image_name: str | int, min_filter, mag_filter, wrapping_x_axis, wrapping_y_axis,
                          file_path: str, generate_mipmap: bool):
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, mag_filter)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrapping_x_axis)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrapping_y_axis)

        image = pilimage.open(os.path.join(file_path, str(image_name)))
        image = image.transpose(pilimage.Transpose.FLIP_TOP_BOTTOM)
        image = image.convert("RGBA")

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width, image.height, 0, GL_RGBA, GL_UNSIGNED_BYTE,
                     image.tobytes())
        if generate_mipmap:
            glGenerateMipmap(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, 0)

        slot = TextureHandler._register_texture(image_name, tex_id)
        return slot, tex_id

    @staticmethod
    def _register_texture(name, tex_id):
        """Gives a freshly created texture its permanent slot and, if there is a free
           texture unit left, binds it right away so that it is usable immediately."""
        slot = len(TextureHandler.slot_id_list)
        TextureHandler.slot_id_list.append(tex_id)
        TextureHandler.slot_unit_list.append(_UNBOUND)
        TextureHandler._slot_last_used.append(TextureHandler._use_counter)

        TextureHandler.name_id_dict[name] = tex_id
        TextureHandler.name_slot_dict[name] = slot

        free_unit = TextureHandler._find_free_unit()
        if free_unit is not None:
            TextureHandler._bind_slot_to_unit(slot, free_unit)
        else:
            TextureHandler._slot_table_dirty = True
        return slot

    @staticmethod
    def _find_free_unit():
        for unit, occupant in enumerate(TextureHandler.unit_slot_list):
            if occupant == _UNBOUND:
                return unit
        return None

    @staticmethod
    def _bind_slot_to_unit(slot, unit):
        previous_occupant = TextureHandler.unit_slot_list[unit]
        if previous_occupant != _UNBOUND:
            TextureHandler.slot_unit_list[previous_occupant] = _UNBOUND

        glActiveTexture(GL_TEXTURE0 + unit)
        glBindTexture(GL_TEXTURE_2D, TextureHandler.slot_id_list[slot])

        TextureHandler.unit_slot_list[unit] = slot
        TextureHandler.slot_unit_list[slot] = unit
        TextureHandler._slot_table_dirty = True

    @staticmethod
    def ensure_resident(slots):
        """Guarantees that every slot in 'slots' is bound to a texture unit before the
           next draw call, evicting the least recently needed textures if it has to.
           Render passes call this with the slots their draw is about to reference.
           Returns True when the residency set changed."""
        if not isinstance(slots, (list, tuple, set, frozenset)):
            slots = [slots]

        wanted = []
        for slot in slots:
            slot = int(slot)
            if 0 <= slot < len(TextureHandler.slot_id_list) and slot not in wanted:
                wanted.append(slot)

        if len(wanted) > TextureHandler.max_texture_units:
            if not TextureHandler._warned_about_thrashing:
                print(f"Warning: a single draw call wants {len(wanted)} textures but only "
                      f"{TextureHandler.max_texture_units} texture units exist. "
                      f"The extra textures will read back as magenta. "
                      f"Split the draw (use more text layers or more shaders) to fix this.")
                TextureHandler._warned_about_thrashing = True
            wanted = wanted[:TextureHandler.max_texture_units]

        TextureHandler._use_counter += 1
        for slot in wanted:
            TextureHandler._slot_last_used[slot] = TextureHandler._use_counter

        missing = [slot for slot in wanted if TextureHandler.slot_unit_list[slot] == _UNBOUND]
        if not missing:
            return False

        protected = set(wanted)
        for slot in missing:
            unit = TextureHandler._find_free_unit()
            if unit is None:
                unit = TextureHandler._pick_evictable_unit(protected)
                if unit is None:
                    break
            TextureHandler._bind_slot_to_unit(slot, unit)

        TextureHandler._update_texture_shader_storage_buffer()
        return True

    @staticmethod
    def _pick_evictable_unit(protected_slots):
        """Finds the unit holding the texture we have needed least recently, skipping
           anything the current draw call still depends on."""
        oldest_unit = None
        oldest_use = None
        for unit, occupant in enumerate(TextureHandler.unit_slot_list):
            if occupant == _UNBOUND:
                return unit
            if occupant in protected_slots:
                continue
            last_used = TextureHandler._slot_last_used[occupant]
            if oldest_use is None or last_used < oldest_use:
                oldest_use = last_used
                oldest_unit = unit
        return oldest_unit

    @staticmethod
    def _update_texture_shader_storage_buffer(force: bool = False):
        """Uploads the slot -> texture unit table that the shaders read to turn a
           mesh's stored slot into the sampler it should actually use."""
        if not force and not TextureHandler._slot_table_dirty:
            return
        if not TextureHandler.texture_shader_storage_buffer:
            return
        # An empty SSBO is not legal, so always keep at least one entry around.
        table = TextureHandler.slot_unit_list if TextureHandler.slot_unit_list else [_UNBOUND]
        data = np.array(table, dtype=np.int32)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextureHandler.texture_shader_storage_buffer)
        glBufferData(GL_SHADER_STORAGE_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
        TextureHandler._slot_table_dirty = False

    @staticmethod
    def get_slot_of(name):
        return TextureHandler.name_slot_dict.get(name)

    @staticmethod
    def get_id_of_slot(slot):
        return TextureHandler.slot_id_list[slot]

    @staticmethod
    def unload_texture(name):
        """Frees a texture's GPU memory and releases its texture unit.
           The slot itself is retired rather than reused, so that any mesh still
           holding it reads back as unbound instead of quietly showing the wrong image."""
        tex_id = TextureHandler.name_id_dict.pop(name, None)
        if tex_id is None:
            return False
        slot = TextureHandler.name_slot_dict.pop(name)
        unit = TextureHandler.slot_unit_list[slot]
        if unit != _UNBOUND:
            glActiveTexture(GL_TEXTURE0 + unit)
            glBindTexture(GL_TEXTURE_2D, 0)
            TextureHandler.unit_slot_list[unit] = _UNBOUND
            TextureHandler.slot_unit_list[slot] = _UNBOUND
        glDeleteTextures(1, [tex_id])
        TextureHandler.slot_id_list[slot] = 0
        TextureHandler._slot_table_dirty = True
        TextureHandler._update_texture_shader_storage_buffer()
        return True
