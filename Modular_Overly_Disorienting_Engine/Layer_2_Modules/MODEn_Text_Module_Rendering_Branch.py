import re
import glfw
from OpenGL.GL import *
import json
import os
import platform
import random
import struct
import subprocess
from Modular_Overly_Disorienting_Engine import TimeHandler
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import TextureHandler,UniformHelper,USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
from enum import Enum
import zipfile

# HANDLER has the big gpu + cpu
# THE LAYERS have parts of the cpu
# THE PARAGRAPHS own the layout and do the bulk packing for their sentences
# THE SENTENCES act as the writing agents that request memory blocks from the layer,
# turn their text into positioned glyphs, and hand those upwards in reveal-sized
# batches so that the paragraph can pack a whole frame's worth in one GPU upload
#
# One thing worth knowing before changing any of this: a sentence lays its text out
# IN FULL the moment the text is added, and revealing only copies already-positioned
# glyphs into the buffer. Laying out progressively instead cannot work, because
# deciding where a word goes needs that word's total width before its first letter
# is placed, and kerning needs the character that comes next. Neither is known yet
# while you are revealing one letter at a time.

_STRUCT_SIZE = 128
MODE_INSTANT_TEXT, MODE_PER_LETTER, MODE_PER_WORD = "instanttext", "perlettertext", "perwordtext"
ALL_INSTANCES_WORD, FIRST_INSTANCE_WORD, LAST_INSTANCE_WORD = "allinstancestext","firstinstancetext","lastinstancetext"
POSITION_CONTINUE="positioncontinue"
SENTENCE_PREVIOUS="targetprevious"
INSTANCE_FIRST = "instancefirst"
INSTANCE_LAST = "instancelast"
INSTANCE_RANDOM = "instancerandom"
INSTANCE_ALL = "instanceall"
INSTANCE_INDEX = "instanceindex"
FONT_KEY_DEFAULT=("Arial",False,False)


class _DelayType(Enum):
    DELAY_NONE = "delaynone"
    DELAY_WAIT_FOR_SENTENCE = "delaywaitforprevious"
    DELAY_WAIT_UNTIL_SIGNAL = "delaywaituntilsignal"
    DELAY_WAIT_FOR_TIME = "delaywaitfortime"
    DELAY_WAIT_UNTIL_TIME = "delaywaituntiltime"

DELAY_NONE=_DelayType.DELAY_NONE
DELAY_WAIT_FOR_SENTENCE=_DelayType.DELAY_WAIT_FOR_SENTENCE
DELAY_WAIT_UNTIL_SIGNAL=_DelayType.DELAY_WAIT_UNTIL_SIGNAL
DELAY_WAIT_FOR_TIME=_DelayType.DELAY_WAIT_FOR_TIME
DELAY_WAIT_UNTIL_TIME=_DelayType.DELAY_WAIT_UNTIL_TIME

MEMORY_BLOCK_SIZE=64

# A laid-out glyph, as produced by Sentence._lay_out_range and consumed by
# Paragraph._process_packets. Positions are relative to the sentence's own origin,
# so moving a sentence or its paragraph is a repack and never a fresh layout.
_GLYPH_OFFSET = 0       # index of this character within the sentence's full text
_GLYPH_SLOT = 1         # texture slot of the font atlas this glyph lives in
_GLYPH_X = 2
_GLYPH_Y = 3
_GLYPH_W = 4
_GLYPH_H = 5
_GLYPH_U = 6
_GLYPH_V = 7
_GLYPH_UW = 8
_GLYPH_VH = 9
_GLYPH_REVEAL_ID = 10
_GLYPH_WORD_ID = 11
_GLYPH_RUN = 12         # the TextRun whose styling applies, so colour stays live
_GLYPH_BLANK = 13       # True for characters that advance the pen but draw nothing


class TextHandler:
    initialized = False
    text_shader_storage_buffer = 0
    _max_characters = 8192
    fonts = {}
    text_layers = []
    _GLOBAL_TEXT_QUAD = None
    # The width, in atlas pixels, that the distance field ramps across. The text
    # fragment shader needs it to work out how crisp to make an edge. Every atlas in
    # this repo was generated with -pxrange 4; load_font keeps the largest it sees.
    distance_range = 4.0
    _warned_about_mixed_distance_ranges = False

    @staticmethod
    def _load_text_handler():
        if not TextHandler.initialized:
            TextHandler.text_shader_storage_buffer = glGenBuffers(1)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
            glBufferData(GL_SHADER_STORAGE_BUFFER, TextHandler._max_characters * _STRUCT_SIZE, None, GL_DYNAMIC_DRAW)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)

            TextHandler._GLOBAL_TEXT_QUAD = Model(None,False,False)
            vertices = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0]
            TextHandler._GLOBAL_TEXT_QUAD.add_vertices(vertices)
            TextHandler._GLOBAL_TEXT_QUAD.connect_vertices([0, 1, 2, 2, 3, 0])

            TextHandler.initialized = True
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

            TextHandler.load_font("Arial")

    @staticmethod
    def _double_space():
        """Doubles the global character buffer, keeping everything already in it.

           Layers hold absolute offsets into this buffer, so the contents have to
           survive the resize: the old buffer is copied into the new one on the GPU
           rather than repacked from the CPU mirrors."""
        old_char_limit = TextHandler._max_characters
        new_char_limit = old_char_limit * 2
        old_byte_size = old_char_limit * _STRUCT_SIZE
        new_byte_size = new_char_limit * _STRUCT_SIZE

        new_ssbo = glGenBuffers(1)
        glBindBuffer(GL_COPY_WRITE_BUFFER, new_ssbo)
        glBufferData(GL_COPY_WRITE_BUFFER, new_byte_size, None, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_COPY_READ_BUFFER, TextHandler.text_shader_storage_buffer)
        glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER, 0, 0, old_byte_size)
        glBindBuffer(GL_COPY_READ_BUFFER, 0)
        glBindBuffer(GL_COPY_WRITE_BUFFER, 0)

        glDeleteBuffers(1, [TextHandler.text_shader_storage_buffer])
        TextHandler.text_shader_storage_buffer = new_ssbo
        TextHandler._max_characters = new_char_limit
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)

    @staticmethod
    def _reserve_space_for(character_count):
        """Grows the global buffer until it can hold character_count characters."""
        while character_count > TextHandler._max_characters:
            TextHandler._double_space()

    @staticmethod
    def _find_font_generator(search_directory):
        """Locates msdf-atlas-gen. The repo ships the Windows build, so look for a
           plain-named binary too before concluding there is none."""
        for candidate_name in ("msdf-atlas-gen.exe", "msdf-atlas-gen"):
            candidate = os.path.join(search_directory, candidate_name)
            if os.path.exists(candidate):
                return candidate
        return None

    @staticmethod
    def load_font(name_of_font, is_bold=False, is_italic=False, font_zip_name=""):
        """Loads a font atlas and its metadata, generating the atlas only if it is not
           already cached in Already_Loaded_Fonts. Returns the atlas's texture slot."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        base_font_dir = os.path.join(project_root, "Layer_0_Modules", "Fonts")
        already_loaded_dir = os.path.join(base_font_dir, "Already_Loaded_Fonts")
        zip_archives_dir = os.path.join(base_font_dir, "Font_Zip_Archives")
        os.makedirs(already_loaded_dir, exist_ok=True)
        cache_filename = f"atlas_{name_of_font}_{is_bold}_{is_italic}"
        png_filename = f"{cache_filename}.png"
        json_filename = f"{cache_filename}.json"
        cached_png_full = os.path.join(already_loaded_dir, png_filename)
        cached_json_full = os.path.join(already_loaded_dir, json_filename)

        if not (os.path.exists(cached_png_full) and os.path.exists(cached_json_full)):
            TextHandler._generate_atlas(name_of_font, font_zip_name, base_font_dir, zip_archives_dir,
                                        already_loaded_dir, current_dir, cached_png_full, cached_json_full)

        try:
            slot = TextureHandler.get_textures(
                png_filename,
                minification_filter=GL_LINEAR,
                magnification_filter=GL_LINEAR,
                file_path=already_loaded_dir,
                generate_mipmap=False
            )
            with open(cached_json_full, 'r') as f:
                metadata = json.load(f)

            glyphs_dict = {int(g['unicode']): g for g in metadata['glyphs'] if 'unicode' in g}
            #for each glyph in the (json file's) metadata glyphs, if "unicode" exists in it,glyphs_dict[unicode integer] = glyph

            # msdf-atlas-gen reports kerning as the EXTRA advance to apply between a
            # specific ordered pair of characters, so it is keyed by the pair and added
            # on top of the first character's own advance.
            kerning_dict = {}
            for pair in metadata.get('kerning', []):
                try:
                    kerning_dict[(int(pair['unicode1']), int(pair['unicode2']))] = float(pair['advance'])
                except (KeyError, TypeError, ValueError):
                    continue

            atlas_metadata = metadata.get('atlas', {})
            font_distance_range = float(atlas_metadata.get('distanceRange', 4.0))
            if font_distance_range != TextHandler.distance_range:
                if not TextHandler._warned_about_mixed_distance_ranges and TextHandler.fonts:
                    print(f"Warning: font '{name_of_font}' was generated with a distance range of "
                          f"{font_distance_range} but other loaded fonts use "
                          f"{TextHandler.distance_range}. One uniform is shared by the whole text "
                          f"pass, so the larger value is used and the other font's edges may soften. "
                          f"Regenerate the atlases with a matching -pxrange to fix this.")
                    TextHandler._warned_about_mixed_distance_ranges = True
                TextHandler.distance_range = max(TextHandler.distance_range, font_distance_range)

            metrics = metadata.get('metrics', {})
            TextHandler.fonts[(name_of_font, is_bold, is_italic)] = {
                'glyphs': glyphs_dict,
                'kerning': kerning_dict,
                'texture_slot': slot,
                'atlas_size': (atlas_metadata.get('width', 1024), atlas_metadata.get('height', 1024)),
                'metrics': metrics,
                'line_height': float(metrics.get('lineHeight', 1.2)),
                'em_size': float(metrics.get('emSize', 1.0)) or 1.0,
                'distance_range': font_distance_range,
            }
            return slot
        except Exception as e:
            print(f"Error loading font data for {name_of_font}: {e}")
            return None

    @staticmethod
    def _generate_atlas(name_of_font, font_zip_name, base_font_dir, zip_archives_dir, already_loaded_dir,
                        generator_dir, cached_png_full, cached_json_full):
        """Last resort when an atlas is not cached. The generator shipped with the repo
           is a Windows executable, so on anything else this is expected to fail; it
           says exactly which file to produce rather than surfacing a subprocess error."""
        print(f"Pregenerated atlas for {name_of_font} not found. Searching zip archives...")
        generator_exe = TextHandler._find_font_generator(generator_dir)
        full_file = None
        extracted_font_path = None

        try:
            if font_zip_name:
                for root, dirs, files in os.walk(zip_archives_dir):
                    for file in files:
                        if file.lower().endswith(".zip"):
                            zip_path = os.path.join(root, file)
                            with zipfile.ZipFile(zip_path, 'r') as z:
                                if font_zip_name in z.namelist():
                                    print(f"Extracting {font_zip_name} from {file}...")
                                    extracted_font_path = z.extract(font_zip_name, already_loaded_dir)
                                    full_file = extracted_font_path
                                    break
                    if full_file: break

                if not full_file:
                    for root, dirs, files in os.walk(base_font_dir):
                        if font_zip_name in files:
                            full_file = os.path.join(root, font_zip_name)
                            break

            if not full_file:
                fallback = os.path.join(base_font_dir, "arial.ttf")
                full_file = fallback if os.path.exists(fallback) else None

            missing_atlas_advice = (
                f"No cached atlas for font '{name_of_font}'.\n"
                f"  Expected these two files to already exist:\n"
                f"    {cached_png_full}\n"
                f"    {cached_json_full}\n"
                f"  Generate them on a machine that can run msdf-atlas-gen with:\n"
                f"    msdf-atlas-gen -font <the .ttf> -type mtsdf -charset-range 32 255 \\\n"
                f"      -json \"{os.path.basename(cached_json_full)}\" "
                f"-imageout \"{os.path.basename(cached_png_full)}\" \\\n"
                f"      -dimensions 1024 1024 -pxrange 4 -yorigin bottom\n"
                f"  then drop both files into Fonts/Already_Loaded_Fonts/."
            )

            if generator_exe is None:
                raise RuntimeError(
                    f"{missing_atlas_advice}\n"
                    f"  The atlas generator is not available here either: the repo ships "
                    f"msdf-atlas-gen.exe, a Windows binary, and no msdf-atlas-gen was found "
                    f"next to the text module (running on {platform.system()}).")

            if not full_file:
                raise RuntimeError(
                    f"{missing_atlas_advice}\n"
                    f"  The source font '{font_zip_name or name_of_font}' was also not found as a "
                    f"file or inside any zip under {base_font_dir}.")

            cmd = [
                generator_exe, "-font", full_file, "-type", "mtsdf",
                "-range", "32-255", "-format", "png",
                "-json", cached_json_full, "-imageout", cached_png_full,
                "-dimensions", "1024", "1024", "-pxrange", "4", "-edgepadding", "2",
                "-pot", "-yorigin", "bottom"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
            except OSError as exc:
                raise RuntimeError(f"{missing_atlas_advice}\n  Could not execute {generator_exe}: {exc}")
            if result.returncode != 0:
                raise RuntimeError(f"{missing_atlas_advice}\n  Generator failed: {result.stderr.strip()}")
        finally:
            if extracted_font_path and os.path.exists(extracted_font_path):
                try:
                    os.remove(extracted_font_path)
                except OSError:
                    pass

    @staticmethod
    def get_font_data(font_key):
        return TextHandler.fonts.get(font_key)

    @staticmethod
    def get_glyph_data(character, font_key):
        """returns glyph data by turning char into its unicode value and using it as a key in the font glyph dictionary"""
        return TextHandler.fonts.get(font_key, {}).get('glyphs', {}).get(ord(character))

    @staticmethod
    def measure_text(text, font_key=FONT_KEY_DEFAULT, size=0.05):
        """Width of a single line of text in layer units, kerning included.
           Widgets need this to centre a caption without guessing at glyph widths."""
        font_data = TextHandler.fonts.get(font_key)
        if not font_data or not text:
            return 0.0
        glyphs = font_data['glyphs']
        kerning = font_data['kerning']
        width = 0.0
        previous_code = None
        for character in text:
            code = ord(character)
            glyph = glyphs.get(code)
            if glyph is None:
                previous_code = None
                continue
            if previous_code is not None:
                width += kerning.get((previous_code, code), 0.0) * size
            width += glyph.get('advance', 0.0) * size
            previous_code = code
        return width

    @staticmethod
    def get_line_height(font_key=FONT_KEY_DEFAULT, size=0.05):
        font_data = TextHandler.fonts.get(font_key)
        if not font_data:
            return size * 1.2
        return font_data['line_height'] * size

    @staticmethod
    def get_ascender(font_key=FONT_KEY_DEFAULT, size=0.05):
        font_data = TextHandler.fonts.get(font_key)
        if not font_data:
            return size
        return float(font_data['metrics'].get('ascender', 0.8)) * size

    @staticmethod
    def _update(dt):
        for layer in TextHandler.text_layers:
            layer._update_layer(dt)


class TextLayer:
    """A text layer is a collection of paragraph with common characteristics.
       Likewise, it is responsible with updating the paragraphs with information regarding time"""
    _total_reserved_characters=0
    DEFAULT_RESERVED_CHARACTERS=2048

    def __init__(self,perspective_matrix,reserved_characters=DEFAULT_RESERVED_CHARACTERS):
        """Pack_into packs and moves individual letters into the CPU buffer
                   Update_gpu replaces the layer's portion of the data in the GPU SSBO with its new CPU buffer"""
        #offers itself an index
        self.layer_index = len(TextHandler.text_layers)
        self.reserved_characters = reserved_characters
        self.buffer_offset = TextLayer._total_reserved_characters
        TextLayer._total_reserved_characters += self.reserved_characters
        TextHandler._reserve_space_for(TextLayer._total_reserved_characters)

        self.free_memory_blocks=list(range(self.reserved_characters//MEMORY_BLOCK_SIZE))
        self._allocated_memory_blocks=set()
        TextHandler.text_layers.append(self)
        self.paragraphs = []

        #reserves itself space on the CPU side.
        #the CPU side is worked on, and the GPU side is only asked to render the already curated data.
        self.cpu_buffer = bytearray(self.reserved_characters * _STRUCT_SIZE)

        # Which font atlases the characters currently in this layer point at. The
        # renderer hands this to the texture handler so the right atlases are bound
        # before the draw, since only a limited number of textures fit in one draw call.
        self._texture_slot_counts = {}

        #the standard MODEn uniform helper
        self._uniform_helper=UniformHelper()
        self._uniform_helper._set_uniforms("text_perspective",perspective_matrix)

    def set_text_perspective_matrix(self,new_matrix):
        self._uniform_helper._set_uniforms("text_perspective", new_matrix)

    def get_uniforms(self,names):
        return self._uniform_helper._get_uniforms(names)

    # ---- the contract the renderer draws through -------------------------------
    def get_character_count(self):
        """How many instances the renderer must draw for this layer.

           The shader reads characters[gl_InstanceID + buffer_offset], so this is the
           high-water mark of the indices in use, not the number of visible glyphs.
           Holes inside that span are zero-filled, which makes them zero-sized quads
           that produce no fragments."""
        if not self._allocated_memory_blocks:
            return 0
        return (max(self._allocated_memory_blocks) + 1) * MEMORY_BLOCK_SIZE

    def get_used_texture_slots(self):
        return [slot for slot, count in self._texture_slot_counts.items() if count > 0]

    def _register_texture_slot(self, slot, delta):
        if slot is None:
            return
        new_count = self._texture_slot_counts.get(slot, 0) + delta
        if new_count <= 0:
            self._texture_slot_counts.pop(slot, None)
        else:
            self._texture_slot_counts[slot] = new_count

    def _pack_into(self, index_in_buffer, texture_slot, use_centre_pivot, gxpos, gypos, gw, gh, u0, v0, u1, v1,
                   reveal_id, word_id, abs_z,
                  pitch, yaw, roll, r, g, b, a,
                  pcx, pcy, pcz, ):
        """This function adds the data of a letter to the cpu buffer"""
        struct.pack_into('<3I29f', self.cpu_buffer, index_in_buffer * _STRUCT_SIZE,
                         # integers

                         #which font atlas, as a texture slot the shader resolves to a bound unit
                         texture_slot,  # 0

                         #spare integer, kept so that the struct stays 128 bytes
                         0,  # 1

                         #rotates around the paragraph or around itself
                         int(use_centre_pivot),  # 2 (0 or 1)

                         # floats

                         # glyph screen position and size
                         gxpos, gypos, gw, gh,  # 3, 4, 5, 6

                         # texture coordinates in atlas
                         u0, v0, u1, v1,  # 7, 8, 9, 10

                         #id used for letter identification in animations
                         reveal_id,  # 11

                         # id used for word identification in animations
                         word_id,  # 12

                         #z coordinate, also used to avoid infighting
                         abs_z,  # 13

                         #rotation angles
                         pitch, yaw, roll,  # 14, 15, 16

                         #color + transparency
                         r, g, b, a,  # 17, 18, 19, 20

                         #paragraph centre
                         pcx, pcy, pcz,  # 21, 22, 23 (Paragraph Centre)

                         #Remaining 8 floats for future bullshit
                         0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                         )

    def _zero_character_slot(self, index_in_buffer):
        """Blanks one character so it draws nothing. A zero width and height makes a
           degenerate quad, which never reaches the fragment stage."""
        start = index_in_buffer * _STRUCT_SIZE
        self.cpu_buffer[start:start + _STRUCT_SIZE] = bytes(_STRUCT_SIZE)

    def _update_gpu(self,start_index,end_index):
        """Updates a smaller part of the big GPU SSBO
           Uses a slice (from start_index*struct_size to end_index*struct_size) of the CPU buffer"""
        if end_index <= start_index:
            return
        #binding the shader storage buffer as the big text buffer from the text handler
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
        start_offset = (self.buffer_offset + start_index) * _STRUCT_SIZE
        data_size = (end_index - start_index) * _STRUCT_SIZE
        slice_start = start_index * _STRUCT_SIZE
        slice_end = end_index * _STRUCT_SIZE
        raw_data = bytes(self.cpu_buffer[slice_start:slice_end])
        glBufferSubData(GL_SHADER_STORAGE_BUFFER, start_offset, data_size, raw_data)


        glBindBuffer(GL_SHADER_STORAGE_BUFFER,0)

    def _upload_everything(self):
        self._update_gpu(0, self.reserved_characters)

    def _update_layer(self,dt):
        for paragraph in self.paragraphs:

            paragraph.update(dt)

    def add_new_paragraph(self,return_index_instead_of_object:bool=False):
        """Adds a paragraph to the layer. A paragraph is a collection of sentences
           A paragraph can house as many sentences as it needs to, but a sentence cannot exist without belonging to a paragraph"""
        new_paragraph=Paragraph(self)
        self.paragraphs.append(new_paragraph)
        if not return_index_instead_of_object:
            return new_paragraph
        else:
            return len(self.paragraphs)

    def remove_paragraph(self, paragraph):
        """Clears a paragraph and drops it from the layer.

           Needed by anything that owns text with a shorter life than the layer, such
           as a UI caption whose widget has just been destroyed: without this the
           glyphs stay in the buffer and go on drawing after their owner is gone."""
        if paragraph not in self.paragraphs:
            return False
        paragraph.clear()
        self.paragraphs.remove(paragraph)
        return True

    def _calculate_memory_block_quantity(self):
        return self.reserved_characters//MEMORY_BLOCK_SIZE

    def _offer_memory_block(self):
        if len(self.free_memory_blocks)==0:
            old_block_count = self._calculate_memory_block_quantity()
            self._double_reserved_characters()
            new_block_count = self._calculate_memory_block_quantity()
            new_blocks = list(range(old_block_count, new_block_count))
            self.free_memory_blocks.extend(new_blocks)
        block = self.free_memory_blocks.pop(0)
        self._allocated_memory_blocks.add(block)
        return block

    def _reclaim_memory_block(self, block):
        if block in self._allocated_memory_blocks:
            self._allocated_memory_blocks.discard(block)
            self.free_memory_blocks.append(block)
            self.free_memory_blocks.sort()

    def _double_reserved_characters(self):
        """Doubles this layer's slice of the global buffer.

           Layers sit back to back in one buffer, so a layer cannot simply grow into
           whatever follows it. Instead it moves to the end of the reserved region and
           re-uploads itself. Character indices are layer-local, so nothing that refers
           to them has to be told; the space left behind is abandoned until
           optimize_layer is worth running on the whole buffer."""
        old_reserved = self.reserved_characters
        new_reserved = old_reserved * 2
        old_buffer = self.cpu_buffer

        self.cpu_buffer = bytearray(new_reserved * _STRUCT_SIZE)
        self.cpu_buffer[0:len(old_buffer)] = old_buffer
        self.reserved_characters = new_reserved

        self.buffer_offset = TextLayer._total_reserved_characters
        TextLayer._total_reserved_characters += new_reserved
        TextHandler._reserve_space_for(TextLayer._total_reserved_characters)

        self._upload_everything()

    def optimize_layer(self):
        """Slides every sentence's characters down to the start of the layer so that the
           space freed by deleted text is usable again.

           This renumbers memory blocks, so every sentence is asked to repack itself
           afterwards. Cheap to call when a layer has churned a lot of text, pointless
           otherwise."""
        sentences = [sentence for paragraph in self.paragraphs for sentence in paragraph._sentences]
        sentences_with_memory = [sentence for sentence in sentences if sentence.memory_blocks]

        self.cpu_buffer = bytearray(self.reserved_characters * _STRUCT_SIZE)
        self._texture_slot_counts = {}
        self._allocated_memory_blocks = set()
        self.free_memory_blocks = list(range(self._calculate_memory_block_quantity()))

        for sentence in sentences_with_memory:
            block_count = len(sentence.memory_blocks)
            sentence.memory_blocks = [self._offer_memory_block() for _ in range(block_count)]

        for paragraph in self.paragraphs:
            paragraph._repack_all()

        self._upload_everything()


class Paragraph:
    """
        Paragraphs are a collection of sentences
        A paragraph is responsible with sharing where (globally) and when(globally) , a sentence is meant and allowed to display,
        and with turning the glyphs its sentences reveal into one bulk write to the buffer.
    """
    __slots__=["_sentences","_packets_to_process","_unfinished_sentence_indexes","_layer","_x","_y","_z",
               "_width","_height","_depth","_is_position_centre","_centre","_bounds"]

    def __init__(self,layer):
        self._sentences=[]
        self._unfinished_sentence_indexes=[]
        self._layer=layer
        self._x=0
        self._y=0
        self._z=0
        # Width is the wrap boundary in layer units. -1 means never wrap, which is what
        # the layout code checks for, so a paragraph with no bounds set behaves as one
        # endless line broken only by newlines the text itself contains.
        self._width=-1
        self._height=-1
        self._depth=-1
        self._is_position_centre = False
        self._centre = (0.0, 0.0, 0.0)
        self._bounds = None
        self._packets_to_process=[]

    # ---- geometry ---------------------------------------------------------------
    def set_position(self, x=USE_OWN, y=USE_OWN, z=USE_OWN):
        """Moves the paragraph. Glyph positions are stored relative to the paragraph,
           so this repacks rather than laying the text out again."""
        if x != USE_OWN: self._x = x
        if y != USE_OWN: self._y = y
        if z != USE_OWN: self._z = z
        self._repack_all()

    def get_position(self):
        return self._x, self._y, self._z

    def set_bounds(self, width=USE_OWN, height=USE_OWN, depth=USE_OWN):
        """Sets the wrap width (and the nominal height/depth).
           Changing the width does force a fresh layout, since it decides where lines
           break."""
        wrap_changed = width != USE_OWN and width != self._width
        if width != USE_OWN: self._width = width
        if height != USE_OWN: self._height = height
        if depth != USE_OWN: self._depth = depth
        if wrap_changed:
            for sentence in self._sentences:
                sentence._relayout()
            self._repack_all()

    def get_bounds(self):
        return self._width, self._height, self._depth

    def get_centre(self):
        return self._centre

    def set_centre_pivot(self, is_position_centre: bool):
        self._is_position_centre = bool(is_position_centre)
        self._repack_all()

    # ---- sentences --------------------------------------------------------------
    def add_sentence(self,text:str,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05,delay_mode=DELAY_WAIT_FOR_SENTENCE,delay_target=None,return_index_instead_of_object:bool=False,continue_previous:bool=True):
        """Adds a sentence to the paragraph. A sentence is a collection of runs
           A paragraph can house as many sentences as it needs to, but a sentence cannot exist without belonging to a paragraph

           By default a new sentence carries on from where the previous one stopped,
           which is what makes a paragraph a paragraph. Every sentence used to start at
           the paragraph's origin, so two sentences in one paragraph drew on top of each
           other. Pass continue_previous=False for a sentence you intend to position
           yourself."""
        new_sentence=Sentence(self)
        if continue_previous and self._sentences:
            previous_sentence = self._sentences[-1]
            end_x, end_y = previous_sentence.get_end_pen()
            new_sentence.x = previous_sentence.x + end_x
            new_sentence.y = previous_sentence.y + end_y
        self._unfinished_sentence_indexes.append(len(self._sentences))
        self._sentences.append(new_sentence)
        new_sentence.set_delay(delay_mode,delay_target)
        new_sentence.add_text(text,font_key,size,r,g,b,a,mode,interval_in_seconds,)
        if not return_index_instead_of_object:
            return new_sentence
        else:
            return len(self._sentences)

    def get_sentences(self):
        return self._sentences

    def update(self,dt):
        if self._unfinished_sentence_indexes:
            still_unfinished = []
            for sentence_index in self._unfinished_sentence_indexes:
                sentence = self._sentences[sentence_index]
                sentence.update(dt,sentence_index)
                # A sentence stays on the list while it still has glyphs to reveal or is
                # waiting on its delay. Without this pruning the list only ever grew, so
                # every finished sentence was still being stepped every single frame.
                if not sentence.is_finished() or not sentence.delay_achieved:
                    still_unfinished.append(sentence_index)
            self._unfinished_sentence_indexes = still_unfinished
            self._process_packets()

    def request_memory_block(self):
        return self._layer._offer_memory_block()

    def _receive_sentence_packet_for_processing(self,packet):
        self._packets_to_process.append(packet)

    # ---- the bulk write ---------------------------------------------------------
    def _process_packets(self):
        """Packs every glyph revealed this frame and uploads the affected span once.

           Sentences hand up laid-out glyphs rather than raw characters, so all this has
           to do is turn each one's sentence-relative position into an absolute one, look
           up the styling that is live right now, and write it."""
        if not self._packets_to_process:
            return

        lowest_index = None
        highest_index = None
        for packet in self._packets_to_process:
            sentence = packet["sentence"]
            for record in packet["glyphs"]:
                index = sentence.buffer_index_of(record[_GLYPH_OFFSET])
                self._write_glyph(sentence, record, index)
                if lowest_index is None or index < lowest_index:
                    lowest_index = index
                if highest_index is None or index > highest_index:
                    highest_index = index
        self._packets_to_process.clear()

        # Revealing text can grow the paragraph, which moves the pivot every glyph
        # rotates around, so the ones already in the buffer need the new centre.
        if self._recalculate_bounds():
            centre_low, centre_high = self._rewrite_centre_only()
            if centre_low is not None:
                lowest_index = centre_low if lowest_index is None else min(lowest_index, centre_low)
                highest_index = centre_high if highest_index is None else max(highest_index, centre_high)

        if lowest_index is not None:
            self._layer._update_gpu(lowest_index, highest_index + 1)

    def _write_glyph(self, sentence, record, index):
        layer = self._layer
        if record[_GLYPH_BLANK]:
            # Spaces and characters the font has no glyph for still own an index, because
            # a character's index is what maps it back to its place in the text.
            layer._zero_character_slot(index)
            return

        run = record[_GLYPH_RUN]
        use_centre_pivot, centre = sentence._pivot_and_centre(self)
        layer._pack_into(
            index,
            record[_GLYPH_SLOT],
            use_centre_pivot,
            self._x + sentence.x + record[_GLYPH_X],
            self._y + sentence.y + record[_GLYPH_Y],
            record[_GLYPH_W], record[_GLYPH_H],
            record[_GLYPH_U], record[_GLYPH_V], record[_GLYPH_UW], record[_GLYPH_VH],
            record[_GLYPH_REVEAL_ID], record[_GLYPH_WORD_ID],
            self._z + sentence.z,
            sentence.pitch, sentence.yaw, sentence.roll,
            run.r, run.g, run.b, run.a,
            centre[0], centre[1], centre[2])
        layer._register_texture_slot(record[_GLYPH_SLOT], 1)

    def _repack_all(self):
        """Rewrites every glyph this paragraph has already revealed. Used when something
           that is applied at pack time changes: the paragraph's position, the pivot mode,
           or a renumbering of memory blocks."""
        self._recalculate_bounds()
        lowest_index = None
        highest_index = None
        self._layer._texture_slot_counts = {
            slot: count for slot, count in self._layer._texture_slot_counts.items() if count > 0}
        for sentence in self._sentences:
            for record in sentence._packed_glyphs:
                index = sentence.buffer_index_of(record[_GLYPH_OFFSET])
                self._write_glyph(sentence, record, index)
                if lowest_index is None or index < lowest_index:
                    lowest_index = index
                if highest_index is None or index > highest_index:
                    highest_index = index
        if lowest_index is not None:
            self._layer._update_gpu(lowest_index, highest_index + 1)

    def _rewrite_centre_only(self):
        """Patches just the three paragraph-centre floats of every packed glyph.
           Slot 21 of the struct, so byte 84, which is why this can skip a full repack."""
        lowest_index = None
        highest_index = None
        for sentence in self._sentences:
            use_centre_pivot, centre = sentence._pivot_and_centre(self)
            if not use_centre_pivot:
                continue
            for record in sentence._packed_glyphs:
                if record[_GLYPH_BLANK]:
                    continue
                index = sentence.buffer_index_of(record[_GLYPH_OFFSET])
                struct.pack_into('<3f', self._layer.cpu_buffer, index * _STRUCT_SIZE + 84,
                                 centre[0], centre[1], centre[2])
                if lowest_index is None or index < lowest_index:
                    lowest_index = index
                if highest_index is None or index > highest_index:
                    highest_index = index
        return lowest_index, highest_index

    def _recalculate_bounds(self):
        """Unions the sentences' own bounding boxes into the paragraph's, and returns
           True when the centre moved."""
        minimum_x = minimum_y = None
        maximum_x = maximum_y = None
        for sentence in self._sentences:
            sentence_bounds = sentence.get_local_bounds()
            if sentence_bounds is None:
                continue
            left, bottom, right, top = sentence_bounds
            left += sentence.x; right += sentence.x
            bottom += sentence.y; top += sentence.y
            minimum_x = left if minimum_x is None else min(minimum_x, left)
            maximum_x = right if maximum_x is None else max(maximum_x, right)
            minimum_y = bottom if minimum_y is None else min(minimum_y, bottom)
            maximum_y = top if maximum_y is None else max(maximum_y, top)

        if minimum_x is None:
            new_bounds = None
            new_centre = (float(self._x), float(self._y), float(self._z))
        else:
            new_bounds = (minimum_x, minimum_y, maximum_x, maximum_y)
            new_centre = (self._x + (minimum_x + maximum_x) * 0.5,
                          self._y + (minimum_y + maximum_y) * 0.5,
                          float(self._z))
        centre_moved = new_centre != self._centre
        self._bounds = new_bounds
        self._centre = new_centre
        return centre_moved

    def get_local_bounds(self):
        """(left, bottom, right, top) of the revealed text, relative to the paragraph."""
        return self._bounds

    def clear(self):
        """Empties every sentence and hands their memory blocks back to the layer."""
        for sentence in self._sentences:
            sentence.clear()
        self._sentences = []
        self._unfinished_sentence_indexes = []
        self._packets_to_process = []
        self._recalculate_bounds()


class Sentence:
    """Holds an ordered collection of runs.
       The sentence is responsible with knowing what , where(relative to the paragraph),
       and when (relative to the paragraph) it is meant to display.

       It lays its text out in full as soon as that text arrives, and revealing only
       decides how much of that finished layout has been handed to the paragraph yet."""
    __slots__=["memory_blocks","paragraph","runs","_full_text","_all_glyphs","_revealed_count",
               "_run_of_character","_local_bounds","_internal_timer","_end_pen",
               "x","y","z","pitch","yaw","roll",
               "delay_mode","delay_target","delay_achieved","paused","is_position_centre",
               "rotate_sentence_around_paragraph","rotate_letters_around_sentence"]

    def __init__(self,paragraph):
        self.memory_blocks=[]
        self.paragraph=paragraph
        self.runs=[]
        self._full_text=""
        self._all_glyphs=[]
        self._revealed_count=0
        self._run_of_character=[]
        self._local_bounds=None
        self._internal_timer=0.0
        # Where the pen finished after laying this sentence out, relative to the
        # sentence's own origin. The paragraph uses it to start the next sentence
        # where this one left off instead of on top of it.
        self._end_pen=(0.0, 0.0)
        self.x=0
        self.y=0
        self.z=0
        self.pitch=0
        self.yaw=0
        self.roll=0
        self.delay_mode=DELAY_WAIT_FOR_SENTENCE
        self.delay_target=SENTENCE_PREVIOUS
        self.delay_achieved=False
        self.paused=False
        self.is_position_centre = False
        self.rotate_sentence_around_paragraph = True
        self.rotate_letters_around_sentence=True

    # ---- text the user can read back -------------------------------------------
    @property
    def text(self):
        """The part of the sentence that has actually been revealed."""
        if self._revealed_count >= len(self._all_glyphs):
            return self._full_text
        return self._full_text[:self._revealed_count]

    @property
    def pending_text(self):
        """The part still waiting to be revealed. Other sentences watch this to know
           when the one they are queued behind has finished."""
        return self._full_text[self._revealed_count:]

    @property
    def full_text(self):
        return self._full_text

    @property
    def _packed_glyphs(self):
        return self._all_glyphs[:self._revealed_count]

    def is_finished(self):
        return self._revealed_count >= len(self._all_glyphs)

    # ---- delays ------------------------------------------------------------------
    def signal_delay_completion(self):
        self.delay_achieved=True

    def set_delay(self,mode=USE_OWN,target=USE_OWN,achieved:bool=USE_OWN):
        if mode != USE_OWN:
            self.delay_mode=mode
        if target != USE_OWN and target is not None:
            # Every mode gets to keep its target. This used to record the target only for
            # DELAY_WAIT_FOR_TIME, so asking a sentence to wait for a specific other
            # sentence silently left it waiting for whatever the default was.
            self.delay_target=target
            if self.delay_mode == DELAY_WAIT_FOR_TIME:
                TimeHandler.set_timed_function(self.signal_delay_completion,target,True,False)
        if achieved != USE_OWN:
            self.delay_achieved=achieved

    def check_delay_achievement(self,own_sentence_index):
        match self.delay_mode:
            case _DelayType.DELAY_NONE:
                #There is no delay
                self.delay_achieved=True

            case _DelayType.DELAY_WAIT_FOR_SENTENCE:
                #The delay is the completion of another sentence
                target_sentence=self.delay_target

                if target_sentence==SENTENCE_PREVIOUS:
                    #The previous sentence in the paragraph, by token turned into index
                    target_index=own_sentence_index-1
                    if target_index>=0:
                        if self.paragraph._sentences[target_index].is_finished():
                            self.delay_achieved=True
                    else:
                        #This branch makes sure that a sentence which has SENTENCE_PREVIOUS as it's mode
                        #while also being the first in the paragraph
                        #is immediately marked as able to be processed because it must wait for none
                        self.delay_achieved=True

                elif isinstance(target_sentence,Sentence):
                    #The specific sentence by instance
                    if target_sentence.is_finished():
                        self.delay_achieved=True
                else:
                    #The specific sentence by index
                    if self.paragraph._sentences[target_sentence].is_finished():
                        self.delay_achieved = True
            case _DelayType.DELAY_WAIT_UNTIL_TIME:
                #The delay is absolute time
                if glfw.get_time()>=self.delay_target:
                    self.delay_achieved=True
            case _DelayType.DELAY_WAIT_FOR_TIME:
                # The delay is handled by the Time Handler, not by the sentence itself.
                pass
            case _DelayType.DELAY_WAIT_UNTIL_SIGNAL:
                # The user is responsible with giving the signal
                pass

    def pause(self):
        self.paused=True
        TimeHandler.pause_function(self.signal_delay_completion)

    def unpause(self):
        self.paused=False
        TimeHandler.unpause_function(self.signal_delay_completion)

    def toggle_pause(self):
        self.paused=not self.paused
        TimeHandler.toggle_pause(self.signal_delay_completion)

    # ---- memory ------------------------------------------------------------------
    def request_memory_block(self):
        self.memory_blocks.append(self.paragraph.request_memory_block())

    def _ensure_memory_blocks(self):
        """Every character owns an index, blanks included, because an index is what ties
           a character back to its place in the text. So the block count follows the
           length of the text and nothing else.

           The old version sized this from the revealed text rather than the whole text,
           which under-allocated and started writing into another sentence's blocks once
           a sentence passed 64 characters."""
        blocks_needed = (len(self._full_text) + MEMORY_BLOCK_SIZE - 1) // MEMORY_BLOCK_SIZE
        while len(self.memory_blocks) < blocks_needed:
            self.request_memory_block()

    def buffer_index_of(self, character_offset):
        """Turns a character's place in the text into its index in the layer's buffer.

           A sentence's blocks are not next to each other, so this has to be worked out
           per character. Deriving one block for a whole batch, as the earlier code did,
           wrote past the end of a block whenever a batch straddled a boundary."""
        block = self.memory_blocks[character_offset // MEMORY_BLOCK_SIZE]
        return block * MEMORY_BLOCK_SIZE + (character_offset % MEMORY_BLOCK_SIZE)

    # ---- runs --------------------------------------------------------------------
    def _add_run(self,length,offset,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05,return_index_instead_of_object:bool=False):
        """Adds a text run to the sentence. A text run is a collection of similar bits of raw data.
           A sentence can house as many text runs as it needs to, but a text run cannot exist without belonging to a sentence"""
        new_run=TextRun(length,offset,font_key,size, r, g, b, a, mode, interval_in_seconds)
        self.runs.append(new_run)
        if not return_index_instead_of_object:
            return new_run
        else:
            return len(self.runs)

    def add_text(self,text,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05):
        """Appends styled text. Identical styling extends the previous run instead of
           making a new one, which keeps the run list short when text arrives in pieces.

           size is an em size in the layer's own units: pixels for a layer built on an
           orthographic matrix, world units for one built on a camera's perspective."""
        if not text:
            return self.runs[-1] if self.runs else None

        start_offset = len(self._full_text)
        new_style = [size, font_key, r, g, b, a, mode, interval_in_seconds]
        run_to_return = None

        if self.runs:
            last_run = self.runs[-1]
            data = last_run._get_all_info()
            #this runs in order to extend the last run if the current run's settings are identical, thus reducing their count
            matching_features=0
            # checks every feature except length and offset
            for index,name_of_data in enumerate(data):
                if name_of_data != "length" and name_of_data != "offset":
                    if data[name_of_data] == new_style[index-2]:
                        matching_features+=1

            #this runs if all of the relevant qualities match
            if matching_features == 8:
                #extends the length of the last run
                last_run._change_length(len(text))
                run_to_return = last_run

        if run_to_return is None:
            # The offset is where this run starts in the sentence's text. It used to be
            # derived from the revealed text, so it pointed at the wrong characters for
            # anything that had not fully appeared yet.
            run_to_return = self._add_run(len(text), start_offset, font_key, size, r, g, b, a, mode,
                                          interval_in_seconds)

        self._full_text += text
        self._ensure_memory_blocks()
        self._relayout()
        return run_to_return

    def _build_run_map(self):
        """One entry per character saying which run styles it, so layout never has to
           search the run list per glyph."""
        run_map = [None] * len(self._full_text)
        for run in self.runs:
            for offset in range(run.offset, min(run.offset + run.length, len(run_map))):
                run_map[offset] = run
        # Anything the runs somehow failed to cover falls back to the nearest run so that
        # layout can still measure it instead of dropping the character.
        fallback = self.runs[-1] if self.runs else None
        for offset, run in enumerate(run_map):
            if run is None:
                run_map[offset] = fallback
        return run_map

    # ---- layout ------------------------------------------------------------------
    def _line_height_of(self, run):
        if run is None:
            return 0.0
        font_data = TextHandler.fonts.get(run.font_key)
        if font_data is None:
            return run.size * 1.2
        return font_data['line_height'] * run.size

    def _advance_of(self, character, run, previous_code):
        """Advance for one character, including the kerning owed to the character before
           it. Returns 0 for anything the font does not know about."""
        if run is None:
            return 0.0
        font_data = TextHandler.fonts.get(run.font_key)
        if font_data is None:
            return 0.0
        code = ord(character)
        glyph = font_data['glyphs'].get(code)
        if glyph is None:
            return 0.0
        advance = float(glyph.get('advance', 0.0)) * run.size
        if previous_code is not None:
            advance += font_data['kerning'].get((previous_code, code), 0.0) * run.size
        return advance

    def _measure_range(self, start, end, run_map):
        """Width of text[start:end]. Word wrapping needs this before it places the
           word's first letter, which is the reason layout cannot be done one revealed
           character at a time."""
        width = 0.0
        previous_code = None
        for offset in range(start, end):
            character = self._full_text[offset]
            width += self._advance_of(character, run_map[offset], previous_code)
            previous_code = ord(character)
        return width

    def _relayout(self):
        """Positions every character of the sentence from scratch.

           Cheap enough to always redo, and always redoing it is what keeps wrapping
           correct when text is appended in pieces: a line break depends on text that
           may only have arrived in a later call."""
        self._run_of_character = self._build_run_map()
        self._all_glyphs = self._lay_out()
        if self._revealed_count > len(self._all_glyphs):
            self._revealed_count = len(self._all_glyphs)
        self._recalculate_local_bounds()

    def _lay_out(self):
        text = self._full_text
        if not text:
            self._end_pen = (0.0, 0.0)
            return []
        run_map = self._run_of_character
        wrap_width = self.paragraph._width
        wrapping_enabled = wrap_width is not None and wrap_width > 0
        # A sentence that continues another one starts partway along a line, but every
        # line after the first still belongs to the paragraph's left margin, and the
        # wrap boundary is still the paragraph's right edge. Both are expressed here in
        # the sentence's own coordinates, which is what layout works in.
        line_start_x = -float(self.x)
        wrap_limit = (wrap_width - float(self.x)) if wrapping_enabled else None

        glyphs = []
        pen_x = 0.0
        # The sentence's origin is the baseline of its first line. Ascenders therefore
        # rise above the y the sentence was placed at, and each new line goes downwards.
        baseline_y = 0.0
        previous_code = None
        reveal_id = 0.0
        word_id = 0.0
        a_word_has_been_placed = False

        offset = 0
        total = len(text)
        while offset < total:
            character = text[offset]
            run = run_map[offset]

            if character == '\n':
                glyphs.append(self._blank_record(offset, reveal_id, word_id, run))
                reveal_id += 1.0
                pen_x = line_start_x
                baseline_y -= self._line_height_of(run)
                previous_code = None
                a_word_has_been_placed = False
                offset += 1
                continue

            if character == ' ':
                # A space keeps the word id of the word it follows, so revealing per word
                # brings a word and its trailing space in together instead of spending a
                # whole interval on the gap.
                glyphs.append(self._blank_record(offset, reveal_id, word_id, run))
                reveal_id += 1.0
                pen_x += self._advance_of(character, run, previous_code)
                previous_code = ord(character)
                offset += 1
                continue

            word_end = offset
            while word_end < total and text[word_end] not in (' ', '\n'):
                word_end += 1

            if wrapping_enabled and pen_x > line_start_x:
                word_width = self._measure_range(offset, word_end, run_map)
                if pen_x + word_width > wrap_limit:
                    pen_x = line_start_x
                    baseline_y -= self._line_height_of(run)
                    # The kerning pair that straddled the break no longer applies.
                    previous_code = None

            if a_word_has_been_placed:
                word_id += 1.0
            a_word_has_been_placed = True

            for character_offset in range(offset, word_end):
                character = text[character_offset]
                run = run_map[character_offset]
                record, pen_x = self._place_character(character, character_offset, run, pen_x, baseline_y,
                                                      previous_code, reveal_id, word_id)
                glyphs.append(record)
                previous_code = ord(character)
                reveal_id += 1.0

            offset = word_end

        self._end_pen = (pen_x, baseline_y)
        return glyphs

    def get_end_pen(self):
        """Where the pen stopped, relative to this sentence's origin."""
        return self._end_pen

    def _place_character(self, character, character_offset, run, pen_x, baseline_y, previous_code,
                         reveal_id, word_id):
        """Turns one character into a positioned quad and returns it with the advanced pen."""
        font_data = TextHandler.fonts.get(run.font_key) if run is not None else None
        if font_data is None:
            return self._blank_record(character_offset, reveal_id, word_id, run), pen_x

        code = ord(character)
        glyph = font_data['glyphs'].get(code)
        if glyph is None:
            return self._blank_record(character_offset, reveal_id, word_id, run), pen_x

        if previous_code is not None:
            pen_x += font_data['kerning'].get((previous_code, code), 0.0) * run.size

        advance = float(glyph.get('advance', 0.0)) * run.size

        if 'planeBounds' not in glyph:
            # A character the atlas has metrics but no image for, a space being the usual
            # one. It still moves the pen and still owns an index.
            return self._blank_record(character_offset, reveal_id, word_id, run), pen_x + advance

        plane_bounds = glyph['planeBounds']
        atlas_bounds = glyph['atlasBounds']
        atlas_width, atlas_height = font_data['atlas_size']
        size = run.size

        record = (
            character_offset,
            font_data['texture_slot'],
            pen_x + plane_bounds['left'] * size,
            baseline_y + plane_bounds['bottom'] * size,
            (plane_bounds['right'] - plane_bounds['left']) * size,
            (plane_bounds['top'] - plane_bounds['bottom']) * size,
            atlas_bounds['left'] / atlas_width,
            atlas_bounds['bottom'] / atlas_height,
            (atlas_bounds['right'] - atlas_bounds['left']) / atlas_width,
            (atlas_bounds['top'] - atlas_bounds['bottom']) / atlas_height,
            reveal_id,
            word_id,
            run,
            False,
        )
        return record, pen_x + advance

    @staticmethod
    def _blank_record(character_offset, reveal_id, word_id, run):
        return (character_offset, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                reveal_id, word_id, run, True)

    def _recalculate_local_bounds(self):
        minimum_x = minimum_y = maximum_x = maximum_y = None
        for record in self._all_glyphs[:self._revealed_count]:
            if record[_GLYPH_BLANK]:
                continue
            left = record[_GLYPH_X]
            bottom = record[_GLYPH_Y]
            right = left + record[_GLYPH_W]
            top = bottom + record[_GLYPH_H]
            minimum_x = left if minimum_x is None else min(minimum_x, left)
            maximum_x = right if maximum_x is None else max(maximum_x, right)
            minimum_y = bottom if minimum_y is None else min(minimum_y, bottom)
            maximum_y = top if maximum_y is None else max(maximum_y, top)
        self._local_bounds = None if minimum_x is None else (minimum_x, minimum_y, maximum_x, maximum_y)

    def get_local_bounds(self):
        """(left, bottom, right, top) of the revealed glyphs, relative to the sentence."""
        return self._local_bounds

    def get_size(self):
        """(width, height) of the revealed text."""
        if self._local_bounds is None:
            return 0.0, 0.0
        left, bottom, right, top = self._local_bounds
        return right - left, top - bottom

    def _pivot_and_centre(self, paragraph):
        """Decides what the shader should rotate this sentence's glyphs around.

           The struct carries one pivot flag and one point, so the two rotation
           preferences are resolved here: around the paragraph wins, then around the
           sentence, and otherwise each glyph spins where it sits."""
        if self.rotate_sentence_around_paragraph:
            return 1, paragraph._centre
        if self.rotate_letters_around_sentence and self._local_bounds is not None:
            left, bottom, right, top = self._local_bounds
            return 1, (paragraph._x + self.x + (left + right) * 0.5,
                       paragraph._y + self.y + (bottom + top) * 0.5,
                       float(paragraph._z + self.z))
        return 0, (0.0, 0.0, 0.0)

    # ---- revealing ---------------------------------------------------------------
    def update(self,dt,sentence_index):
        if self.paused:
            return
        if not self.delay_achieved:
            self.check_delay_achievement(sentence_index)
            if not self.delay_achieved:
                return
        if self._revealed_count >= len(self._all_glyphs):
            return

        self._internal_timer += dt
        first_newly_revealed = self._revealed_count
        total = len(self._all_glyphs)

        while self._revealed_count < total:
            record = self._all_glyphs[self._revealed_count]
            run = record[_GLYPH_RUN]
            interval = run.interval_in_seconds if run is not None else 0.0

            if run is None or run.mode == MODE_INSTANT_TEXT or interval is None or interval <= 0.0:
                # Instant means instant. The previous version still spent one interval per
                # character in this mode, so "instant" text typed itself out slowly.
                while (self._revealed_count < total
                       and self._all_glyphs[self._revealed_count][_GLYPH_RUN] is run):
                    self._revealed_count += 1
                continue

            if self._internal_timer < interval:
                break

            if run.mode == MODE_PER_WORD:
                word_id = record[_GLYPH_WORD_ID]
                while (self._revealed_count < total
                       and self._all_glyphs[self._revealed_count][_GLYPH_RUN] is run
                       and self._all_glyphs[self._revealed_count][_GLYPH_WORD_ID] == word_id):
                    self._revealed_count += 1
            else:
                self._revealed_count += 1
            self._internal_timer -= interval

        if self._revealed_count > first_newly_revealed:
            self._recalculate_local_bounds()
            self._send_packet_for_processing(self._all_glyphs[first_newly_revealed:self._revealed_count])

    def reveal_everything(self):
        """Skips whatever is left of the typewriter effect."""
        if self._revealed_count >= len(self._all_glyphs):
            return
        first_newly_revealed = self._revealed_count
        self._revealed_count = len(self._all_glyphs)
        self._recalculate_local_bounds()
        self._send_packet_for_processing(self._all_glyphs[first_newly_revealed:])
        self.paragraph._process_packets()

    def _send_packet_for_processing(self,glyphs):
        """sends all the necessary characters upwards in the hierarchy in order for the paragraph to handle the bulk process"""
        packet = {
            "sentence": self,
            "glyphs": glyphs,
            "font_settings": glyphs[0][_GLYPH_RUN]._get_all_info() if glyphs and glyphs[0][_GLYPH_RUN] else None,
            "local_pos": (self.x, self.y, self.z),
            "local_rot": (self.pitch, self.yaw, self.roll),
            "flags": (self.is_position_centre, self.rotate_sentence_around_paragraph,
                      self.rotate_letters_around_sentence),
            "characters": "".join(self._full_text[record[_GLYPH_OFFSET]] for record in glyphs),
        }
        self.paragraph._receive_sentence_packet_for_processing(packet)

    # ---- mutation ----------------------------------------------------------------
    def set_position(self, x=USE_OWN, y=USE_OWN, z=USE_OWN):
        if x != USE_OWN: self.x = x
        if y != USE_OWN: self.y = y
        if z != USE_OWN: self.z = z
        self.paragraph._repack_all()

    def set_rotation(self, pitch=USE_OWN, yaw=USE_OWN, roll=USE_OWN):
        if pitch != USE_OWN: self.pitch = pitch
        if yaw != USE_OWN: self.yaw = yaw
        if roll != USE_OWN: self.roll = roll
        self.paragraph._repack_all()

    def set_colour(self, r=USE_OWN, g=USE_OWN, b=USE_OWN, a=USE_OWN):
        """Recolours the whole sentence. Colour lives at slot 17 of the struct, so this
           patches four floats per glyph instead of repacking them."""
        for run in self.runs:
            run._set_color(r, g, b, a)
        lowest_index = None
        highest_index = None
        for record in self._all_glyphs[:self._revealed_count]:
            if record[_GLYPH_BLANK]:
                continue
            run = record[_GLYPH_RUN]
            index = self.buffer_index_of(record[_GLYPH_OFFSET])
            struct.pack_into('<4f', self.paragraph._layer.cpu_buffer, index * _STRUCT_SIZE + 68,
                             run.r, run.g, run.b, run.a)
            lowest_index = index if lowest_index is None else min(lowest_index, index)
            highest_index = index if highest_index is None else max(highest_index, index)
        if lowest_index is not None:
            self.paragraph._layer._update_gpu(lowest_index, highest_index + 1)

    # Both spellings, because the rest of the engine is inconsistent about it.
    set_color = set_colour

    def _get_substring(self,regex_string,ignore_upper_lower_case:bool=True):
        if ignore_upper_lower_case:
            return re.findall(regex_string,self._full_text,re.IGNORECASE)
        else:
            return re.findall(regex_string, self._full_text)

    def _erase_text(self,regex_string,instance=INSTANCE_FIRST,ignore_upper_lower_case:bool=True):
        """Blanks the characters matching a pattern without disturbing anything around
           them: the text keeps its length so every other character stays at the index
           it was packed at. Returns how many matches were erased."""
        flags = re.IGNORECASE if ignore_upper_lower_case else 0
        matches = list(re.finditer(regex_string, self._full_text, flags))
        if not matches:
            return 0

        if instance == INSTANCE_FIRST:
            chosen = [matches[0]]
        elif instance == INSTANCE_LAST:
            chosen = [matches[-1]]
        elif instance == INSTANCE_ALL:
            chosen = matches
        elif instance == INSTANCE_RANDOM:
            chosen = [random.choice(matches)]
        elif isinstance(instance, int):
            if instance < 0 or instance >= len(matches):
                return 0
            chosen = [matches[instance]]
        else:
            chosen = [matches[0]]

        erased_offsets = set()
        for match in chosen:
            erased_offsets.update(range(match.start(), match.end()))

        layer = self.paragraph._layer
        lowest_index = None
        highest_index = None
        for position, record in enumerate(self._all_glyphs):
            if record[_GLYPH_OFFSET] not in erased_offsets:
                continue
            if not record[_GLYPH_BLANK]:
                layer._register_texture_slot(record[_GLYPH_SLOT], -1)
            self._all_glyphs[position] = self._blank_record(
                record[_GLYPH_OFFSET], record[_GLYPH_REVEAL_ID], record[_GLYPH_WORD_ID], record[_GLYPH_RUN])
            if position < self._revealed_count:
                index = self.buffer_index_of(record[_GLYPH_OFFSET])
                layer._zero_character_slot(index)
                lowest_index = index if lowest_index is None else min(lowest_index, index)
                highest_index = index if highest_index is None else max(highest_index, index)

        # Replacing the characters with spaces keeps the text the same length, which is
        # what lets every surviving glyph stay where it already is.
        text_as_list = list(self._full_text)
        for offset in erased_offsets:
            text_as_list[offset] = ' '
        self._full_text = "".join(text_as_list)

        self._recalculate_local_bounds()
        if lowest_index is not None:
            layer._update_gpu(lowest_index, highest_index + 1)
        return len(chosen)

    def erase_text(self, target, instance=INSTANCE_FIRST, whole_words_only: bool = True):
        """Erases a literal piece of text. Escapes the target, so punctuation in it is
           taken literally rather than as a pattern."""
        pattern = re.escape(str(target))
        if whole_words_only:
            pattern = rf"\b{pattern}\b"
        return self._erase_text(pattern, instance)

    def clear(self):
        """Blanks the sentence and gives its memory blocks back to the layer."""
        layer = self.paragraph._layer
        lowest_index = None
        highest_index = None
        for record in self._all_glyphs[:self._revealed_count]:
            index = self.buffer_index_of(record[_GLYPH_OFFSET])
            if not record[_GLYPH_BLANK]:
                layer._register_texture_slot(record[_GLYPH_SLOT], -1)
            layer._zero_character_slot(index)
            lowest_index = index if lowest_index is None else min(lowest_index, index)
            highest_index = index if highest_index is None else max(highest_index, index)
        if lowest_index is not None:
            layer._update_gpu(lowest_index, highest_index + 1)

        for block in self.memory_blocks:
            layer._reclaim_memory_block(block)
        self.memory_blocks = []
        self.runs = []
        self._full_text = ""
        self._all_glyphs = []
        self._run_of_character = []
        self._revealed_count = 0
        self._internal_timer = 0.0
        self._local_bounds = None

    def set_text(self, text, font_key=FONT_KEY_DEFAULT, size=0.05, r=1.0, g=1.0, b=1.0, a=1.0,
                 mode=MODE_INSTANT_TEXT, interval_in_seconds=0.05):
        """Throws away what the sentence held and writes something else in its place."""
        self.clear()
        self.delay_achieved = True
        return self.add_text(text, font_key, size, r, g, b, a, mode, interval_in_seconds)


class TextRun:
    """Holds bundles of similar raw data for sentences
       The text run is responsible with knowing how to display an arbitrary string of a set length"""
    __slots__=["length","offset","size","font_key","r","g","b","a","mode","interval_in_seconds"]
    def __init__(self,length,offset,font_key,size,r,g,b,a,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.1):
        self.length=length
        self.offset=offset
        self.font_key=font_key
        self.size=size
        self.r = r
        self.g = g
        self.b = b
        self.a = a
        self.mode=mode
        self.interval_in_seconds=interval_in_seconds
    def _get_all_info(self):
        return {slot: getattr(self, slot) for slot in self.__slots__}
    def _set_length(self,new_length):
        self.length=new_length
    def _change_length(self,length):
        self.length+=length
    def _set_offset(self, new_offset):
        self.offset = new_offset
    def _change_offset(self, offset):
        self.offset += offset
    def _set_mode(self,mode):
        self.mode=mode
    def _set_interval(self,new_interval):
        self.interval_in_seconds=new_interval
    def _change_interval(self,interval):
        self.interval_in_seconds+=interval
    def _set_color(self,r=USE_OWN,g=USE_OWN,b=USE_OWN,a=USE_OWN):
        self.r = r if r != USE_OWN else self.r
        self.g = g if g != USE_OWN else self.g
        self.b = b if b != USE_OWN else self.b
        self.a = a if a != USE_OWN else self.a
    def _change_color(self,r=0,g=0,b=0,a=0):
        self.r += r
        self.g += g
        self.b += b
        self.a += a
    def _get_update_data(self):
        return self.length,self.mode,self.interval_in_seconds
