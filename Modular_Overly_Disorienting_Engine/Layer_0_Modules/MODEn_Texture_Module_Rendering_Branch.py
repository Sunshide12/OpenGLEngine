# TODO
#  Add a way to unload textures from residence/memory
#  Add a way to create textures as dynamic load instead of always static_draw (additional note for clarity below)
from OpenGL.GL import *
from OpenGL.GL.ARB.bindless_texture import *
from PIL import Image as pilimage
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import USE_OWN
import numpy as np


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
       """
    initialized = False
    name_id_dict = {}  # texture name → tex_id
    id_handle_dict = {}  # tex_id → handle
    name_slot_dict = {}  # texture name → SSBO index
    texture_handles = []  # Python list for bindless handles
    texture_shader_storage_buffer = 0
    default_texture_file_path = "E:/Vlad/python/other/Modular_Overly_Disorienting_Engine"

    @staticmethod
    def _load_texture_handler():

        if not TextureHandler.initialized:
            TextureHandler.texture_shader_storage_buffer = glGenBuffers(1)
            TextureHandler.get_textures("placeholder.png",file_path="E:/Vlad/python/other/Modular_Overly_Disorienting_Engine") #TODO change so that it take the relative path
            data = np.array(TextureHandler.texture_handles, dtype=np.uint64)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextureHandler.texture_shader_storage_buffer)
            glBufferData(GL_SHADER_STORAGE_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, TextureHandler.texture_shader_storage_buffer)
            TextureHandler.initialized = True
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    @staticmethod
    def get_textures(image_names: str | list |np.uintc | int , minification_filter=GL_NEAREST_MIPMAP_NEAREST,
                     magnification_filter=GL_NEAREST, wrapping_x_axis=GL_CLAMP_TO_EDGE,
                     wrapping_y_axis=GL_CLAMP_TO_EDGE, file_path: str = USE_OWN,generate_mipmap:bool=True,return_id_with_slot:bool=False):
        """Loads a texture is it wasn't yet loaded
        Returns the slot of an image, which shaders want.
        Can return the OpenGL id alongside it for other purposes if needed."""

        if file_path == USE_OWN:
            file_path = TextureHandler.default_texture_file_path
        if isinstance(image_names, str) or isinstance(image_names,int) or isinstance(image_names,np.uintc):
            if hasattr(image_names, 'item'):
                image_names = image_names.item()
            if image_names in TextureHandler.name_id_dict:
                if not return_id_with_slot:
                    return TextureHandler.name_slot_dict[image_names]
                else:
                    return TextureHandler.name_slot_dict[image_names],TextureHandler.name_id_dict[image_names]
            else:

                slot,tex_id = TextureHandler._generate_texture(image_names, minification_filter, magnification_filter,
                                                        wrapping_x_axis, wrapping_y_axis, file_path,generate_mipmap,return_id_with_slot)
                TextureHandler._update_texture_shader_storage_buffer()
                if not return_id_with_slot:
                    return slot
                else:
                    return slot,tex_id
        else:
            made_textures = False
            slots = []
            tex_ids=[]
            for name in image_names:
                if name in TextureHandler.name_id_dict:
                    slots.append(TextureHandler.id_handle_dict[TextureHandler.name_id_dict[name]])
                    if return_id_with_slot:
                        tex_ids.append(TextureHandler.name_id_dict[name])

                else:
                    made_textures = True
                    slot,tex_id=TextureHandler._generate_texture(name, minification_filter, magnification_filter,
                                                                  wrapping_x_axis, wrapping_y_axis, file_path,generate_mipmap,return_id_with_slot)
                    slots.append(slot)
                    if return_id_with_slot:
                        tex_ids.append(tex_id)

            if made_textures:
                TextureHandler._update_texture_shader_storage_buffer()
            if return_id_with_slot:
                return slots,tex_ids
            else:
                return slots

    @staticmethod
    def _update_texture_shader_storage_buffer():
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextureHandler.texture_shader_storage_buffer)
        # Convert 64-bit handles to two 32-bit uints each
        data = np.array(TextureHandler.texture_handles, dtype=np.uint64)
        glBufferData(GL_SHADER_STORAGE_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
    @staticmethod
    def _generate_texture(image_name: str|int, min_filter, mag_filter, wrapping_x_axis, wrapping_y_axis, file_path: str,generate_mipmap:bool,return_id_with_slot:bool=False):
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)


        if type(image_name)==str:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, mag_filter)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrapping_x_axis)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrapping_y_axis)



            # Bindless

            image = pilimage.open(f"{file_path}/{image_name}")
            image = image.transpose(pilimage.Transpose.FLIP_TOP_BOTTOM)
            image = image.convert("RGBA")

            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width, image.height, 0, GL_RGBA, GL_UNSIGNED_BYTE,
                         image.tobytes())
            if generate_mipmap:
                glGenerateMipmap(GL_TEXTURE_2D)
            texture_handle = glGetTextureHandleARB(tex_id)
            glMakeTextureHandleResidentARB(texture_handle)
        else:
            # Now use actual GL constants for filters
            glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, min_filter, mag_filter)
            # Hardcode or use the hijacked wrapping args for the actual filters
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            texture_handle = glGetTextureHandleARB(tex_id)

        # Get the bindless handle


        # Store handle in list
        slot = len(TextureHandler.texture_handles)  # the SSBO index
        TextureHandler.texture_handles.append(texture_handle)

        # Store mappings
        TextureHandler.name_id_dict[image_name] = tex_id
        TextureHandler.id_handle_dict[tex_id] = texture_handle
        TextureHandler.name_slot_dict[image_name] = slot
        if return_id_with_slot:
            return slot,tex_id
        else:
            return slot,None

