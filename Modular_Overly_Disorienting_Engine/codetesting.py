# from OpenGL.GL import *
# import json
# import os
# import subprocess
# import struct
# from Modular_Overly_Disorienting_Engine.Layer_0_Modules import TextureHandler, UniformHelper, USE_OWN
# from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
# from pyglm import glm
# import zipfile
#
# _STRUCT_SIZE = 128
# INSTANT_TEXT, PER_LETTER, PER_WORD = "instanttext", "perlettertext", "perwordtext"
# ALL_INSTANCES_WORD, FIRST_INSTANCE_WORD, LAST_INSTANCE_WORD = "allinstancestext", "firstinstancetext", "lastinstancetext"
# ERASE_ACTION = "ERASE"
#
#
# class TextHandler:
#     initialized = False
#     text_shader_storage_buffer = 0
#     max_characters = 20000
#     fonts = {}
#     text_layers = []
#     _GLOBAL_TEXT_QUAD = None
#
#     @staticmethod
#     def _load_text_handler():
#         if not TextHandler.initialized:
#             TextHandler.text_shader_storage_buffer = glGenBuffers(1)
#             glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
#             glBufferData(GL_SHADER_STORAGE_BUFFER, TextHandler.max_characters * _STRUCT_SIZE, None, GL_DYNAMIC_DRAW)
#             glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)
#
#             TextHandler._GLOBAL_TEXT_QUAD = Model(None, False, False)
#             vertices = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0]
#             TextHandler._GLOBAL_TEXT_QUAD.add_vertices(vertices)
#             TextHandler._GLOBAL_TEXT_QUAD.connect_vertices([0, 1, 2, 2, 3, 0])
#
#             TextHandler.initialized = True
#             glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
#
#             TextHandler.load_font("Arial")
#
#     @staticmethod
#     def load_font(name_of_font, is_bold=False, is_italic=False, font_zip_name=""):
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         project_root = os.path.dirname(current_dir)
#         base_font_dir = os.path.join(project_root, "Layer_0_Modules", "Fonts")
#         already_loaded_dir = os.path.join(base_font_dir, "Already_Loaded_Fonts")
#         zip_archives_dir = os.path.join(base_font_dir, "Font_Zip_Archives")
#         os.makedirs(already_loaded_dir, exist_ok=True)
#         generator_exe = os.path.join(current_dir, "msdf-atlas-gen.exe")
#         cache_filename = f"atlas_{name_of_font}_{is_bold}_{is_italic}"
#         png_filename = f"{cache_filename}.png"
#         json_filename = f"{cache_filename}.json"
#         cached_png_full = os.path.join(already_loaded_dir, png_filename)
#         cached_json_full = os.path.join(already_loaded_dir, json_filename)
#         if not (os.path.exists(cached_png_full) and os.path.exists(cached_json_full)):
#             print(f"Pregenerated atlas for {name_of_font} not found. Searching zip archives...")
#             full_file = None
#             extracted_font_path = None
#
#             try:
#                 for root, dirs, files in os.walk(zip_archives_dir):
#                     for file in files:
#                         if file.lower().endswith(".zip"):
#                             zip_path = os.path.join(root, file)
#                             with zipfile.ZipFile(zip_path, 'r') as z:
#                                 members = z.namelist()
#                                 if font_zip_name in members:
#                                     print(f"Extracting {font_zip_name} from {file}...")
#                                     extracted_font_path = z.extract(font_zip_name, already_loaded_dir)
#                                     full_file = extracted_font_path
#                                     break
#                     if full_file: break
#
#                 if not full_file:
#                     for root, dirs, files in os.walk(base_font_dir):
#                         if font_zip_name in files:
#                             full_file = os.path.join(root, font_zip_name)
#                             break
#
#                 if not full_file or not os.path.exists(full_file):
#                     fallback = os.path.join(base_font_dir, "arial.ttf")
#                     full_file = fallback if os.path.exists(fallback) else None
#
#                 if not full_file:
#                     raise Exception(f"Source '{font_zip_name}' not found as a real file or inside a zip.")
#
#                 cmd = [
#                     generator_exe, "-font", full_file, "-type", "mtsdf",
#                     "-range", "32-255", "-format", "png",
#                     "-json", cached_json_full, "-imageout", cached_png_full,
#                     "-dimensions", "1024", "1024", "-pxrange", "4", "-edgepadding", "2",
#                     "-pot", "-yorigin", "bottom"
#                 ]
#                 result = subprocess.run(cmd, capture_output=True, text=True)
#                 if result.returncode != 0:
#                     raise Exception(f"Generator error: {result.stderr}")
#
#             except Exception as e:
#                 raise Exception(f"Critical error generating font {name_of_font}: {e}")
#             finally:
#
#                 if extracted_font_path and os.path.exists(extracted_font_path):
#                     try:
#                         os.remove(extracted_font_path)
#                     except:
#                         pass
#
#         try:
#             slot, tex_id = TextureHandler.get_textures(
#                 png_filename,
#                 minification_filter=GL_LINEAR,
#                 magnification_filter=GL_LINEAR,
#                 file_path=already_loaded_dir,
#                 generate_mipmap=False,
#                 return_id_with_slot=True
#             )
#             actual_handle = TextureHandler.id_handle_dict[tex_id]
#             with open(cached_json_full, 'r') as f:
#                 metadata = json.load(f)
#
#             glyphs_dict = {int(g['unicode']): g for g in metadata['glyphs'] if 'unicode' in g}
#             # for each glyph in the (json file's) metadata glyphs, if "unicode" exists in it,glyphs_dict[unicode integer] = glyph
#
#             TextHandler.fonts[(name_of_font, is_bold, is_italic)] = {
#                 'glyphs': glyphs_dict,
#                 'texture_handle': actual_handle,
#                 'atlas_size': (metadata['atlas']['width'], metadata['atlas']['height'])
#             }
#             return slot
#         except Exception as e:
#             print(f"Error loading font data for {name_of_font}: {e}")
#             return None
#
#     @staticmethod
#     def _update(dt):
#         for layer in TextHandler.text_layers:
#             layer._update_layer(dt)
#
#
# class TextLayer:
#     _total_text_characters = 0
#
#     # TODO remove the arbitrary character limit on everything by dynamically increasing buffers once they get full
#     def __init__(self, text_perspective_matrix,
#                  available_characters=2000):  # TODO text_perspective_matrix should be camera or perspective matrix
#         self.layer_index = len(TextHandler.text_layers)
#         if TextLayer._total_text_characters + available_characters > TextHandler.max_characters:
#             raise MemoryError(f"SSBO Overflow: Cannot allocate {available_characters} more characters.")
#
#         self.available_characters = available_characters
#         self.buffer_offset = TextLayer._total_text_characters
#         TextLayer._total_text_characters += available_characters
#
#         TextHandler.text_layers.append(self)
#         self.paragraphs = []
#
#         # reserves itself space
#         self.cpu_buffer = bytearray(available_characters * _STRUCT_SIZE)
#
#         # index in own buffer
#         self.next_char_index = 0
#
#         self._uniform_helper = UniformHelper()
#         self._uniform_helper._set_uniforms("text_perspective", text_perspective_matrix)
#
#     def set_text_perspective_matrix(self, new_matrix):
#         self._uniform_helper._set_uniforms("text_perspective", new_matrix)
#
#     def get_uniforms(self, names):
#         return self._uniform_helper._get_uniforms(names)
#
#     def pack_into(self, struct_size_multiplied_by, gxpos, gypos, gw, gh, u0, v0, u1, v1,
#                   h_low, h_high, reveal_id, word_id, abs_z,
#                   pitch, yaw, roll, r, g, b, a,
#                   pcx, pcy, pcz, use_centre_pivot):
#         """This function adds the data of a letter to the cpu buffer"""
#         # struct_size_multiplied_by is usually an index integer
#         struct.pack_into('<3I29f', self.cpu_buffer, struct_size_multiplied_by * _STRUCT_SIZE,
#                          # integers
#                          # handles
#                          h_low,  # 0
#                          h_high,  # 1
#
#                          # rotates around the paragraph or around itself
#                          int(use_centre_pivot),  # 2 (0 or 1)
#
#                          # floats
#
#                          # glyph screen position and size
#                          gxpos, gypos, gw, gh,  # 3, 4, 5, 6
#
#                          # texture coordinates in atlas
#                          u0, v0, u1, v1,  # 7, 8, 9, 10
#
#                          # id used for letter identification in animations
#                          reveal_id,  # 11
#
#                          # id used for word identification in animations
#                          word_id,  # 12
#
#                          # z coordinate, also used to avoid infighting
#                          abs_z,  # 13
#
#                          # rotation angles
#                          pitch, yaw, roll,  # 14, 15, 16
#
#                          # color + transparency
#                          r, g, b, a,  # 17, 18, 19, 20
#
#                          # paragraph centre
#                          pcx, pcy, pcz,  # 21, 22, 23 (Paragraph Centre)
#
#                          # Remaining 8 floats for future bullshit
#                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
#                          )
#
#     # TODO add a run system
#     def add_new_paragraph(self, text, x=0, y=100, z=0.0, font_size=64, max_paragraph_length=500,
#                           font_bold_italic_tuple=("Arial", False, False), mode=INSTANT_TEXT, interval=0.05,
#                           pitch=0.0, yaw=0.0, roll=0.0,
#                           red=1.0, green=1.0, blue=1.0, alpha=1.0,
#                           use_centre_pivot=1):
#         """Adds a new paragraph to the text layer."""
#         if isinstance(use_centre_pivot, bool):
#             if use_centre_pivot:
#                 use_centre_pivot = 1
#             else:
#                 use_centre_pivot = 0
#         else:
#             if use_centre_pivot != 1 and use_centre_pivot != 0:
#                 raise ValueError(
#                     f"use_centre_pivot when creating paragraph with text {text} needs to be 0,1 or a boolean")
#         # paragraph preparations by setting starting values
#         p_idx = len(self.paragraphs)
#         start_buffer_index = self.next_char_index
#
#         p = {
#             'typing_x': x, 'typing_y': y, 'typing_z': z,
#             'start_char_index': start_buffer_index,
#             'char_count': 0, 'total_char_reserved': 0,
#             'current_text': text,
#             'max_paragraph_length': max_paragraph_length,
#             'pending_char_queue': [], 'timer': 0.0, 'interval': interval, 'mode': mode,
#             'pitch': pitch, 'yaw': yaw, 'roll': roll,
#             'r': red, 'g': green, 'b': blue, 'a': alpha,
#             'font_size': font_size, 'font_key': font_bold_italic_tuple,
#             'centre_x': x, 'centre_y': y,
#             'use_centre_pivot': use_centre_pivot
#         }
#         self.paragraphs.append(p)
#         typing_x, typing_y = x, y
#         reveal_id, word_id = 0.0, 0.0
#         prepared_chars = []
#         min_x, max_x = float('inf'), float('-inf')
#         min_y, max_y = float('inf'), float('-inf')
#
#         # line processing in 2d
#         lines = text.split('\n')
#         for line in lines:
#             words = line.split(' ')
#             # word processing
#             for i, word in enumerate(words):
#                 if not word and i != 0: continue
#
#                 word_width = self.calculate_word_width(word, font_size, font_bold_italic_tuple)
#
#                 # starts writing on the next line (font size*1.2) if the word position+width exceeds the paragraph length
#                 if typing_x + word_width > x + max_paragraph_length:
#                     typing_x, typing_y = x, typing_y - (font_size * 1.2)
#
#                 # character processing
#                 for char in word:
#                     char_idx = self.next_char_index
#                     char_width = self.calculate_word_width(char, font_size, font_bold_italic_tuple)
#
#                     # calculates paragraph bounds
#                     min_x, max_x = min(min_x, typing_x), max(max_x, typing_x + char_width)
#                     min_y, max_y = min(min_y, typing_y - (font_size * 1.2)), max(max_y, typing_y)
#
#                     prepared_chars.append((char, font_bold_italic_tuple, font_size, typing_x, typing_y, z,
#                                            reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha, char_idx))
#                     typing_x += char_width
#                     self.next_char_index += 1
#                     p['total_char_reserved'] += 1
#                     reveal_id += 1.0
#
#                 # space character processing
#                 if i < len(words) - 1:
#                     space_width = self.calculate_word_width(' ', font_size, font_bold_italic_tuple)
#                     prepared_chars.append((' ', font_bold_italic_tuple, font_size, typing_x, typing_y, z,
#                                            reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha,
#                                            self.next_char_index))
#                     typing_x += space_width
#                     self.next_char_index += 1
#                     p['total_char_reserved'] += 1
#                     reveal_id += 1.0
#                     word_id += 1.0
#             word_id += 1.0
#             # sets the writing to begin from the next line once all words are done on the previous line
#             typing_x, typing_y = x, typing_y - (font_size * 1.2)
#
#         # centre coordinate calculation
#         if max_x > min_x:
#             p['centre_x'], p['centre_y'] = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
#
#         # if the mode is instant, a request for all the prepared characters to be processed is made immediately.
#         # Othersise, they are added to the pending character queue
#         if mode == INSTANT_TEXT:
#             for args in prepared_chars:
#                 self._process_char_to_gpu(p_idx, *args, upload_now=False)
#             self.update_gpu()
#         else:
#             p['pending_char_queue'] = prepared_chars
#
#         return p_idx
#
#     def get_font_data(self, font_key):
#         return TextHandler.fonts.get(font_key)
#
#     def _process_char_to_gpu(self, p_idx, char, font_key, font_size, world_x, world_y, world_z=0.0,
#                              reveal_id=0.0, word_id=0.0, pitch=0.0, yaw=0.0, roll=0.0,
#                              r=1.0, g=1.0, b=1.0, a=1.0,
#                              specific_index=0, *, upload_now=False):
#         """retrieves and formats the necessary data to send to the packing function"""
#         p = self.paragraphs[p_idx]
#
#         font_data = self.get_font_data(font_key)
#         if not font_data: return 0
#         glyph_data = font_data['glyphs'].get(ord(char))
#         if not glyph_data: return 0
#
#         pcx = p.get('centre_x', world_x)
#         pcy = p.get('centre_y', world_y)
#         pcz = p.get('typing_z_start', world_z)
#         use_centre = p.get('use_centre_pivot')
#
#         handle = font_data.get('texture_handle', 0)
#         atlas_width, atlas_height = font_data['atlas_size']
#         advance = glyph_data.get('advance', 0) * font_size
#
#         h_low = (handle & 0xFFFFFFFF)
#         h_high = ((handle >> 32) & 0xFFFFFFFF)
#
#         # if no planebounds, send
#         if 'planeBounds' not in glyph_data:
#             self.pack_into(specific_index, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
#                            int(h_low), int(h_high),
#                            reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
#                            pcx, pcy, pcz, int(use_centre))
#         else:
#             planebounds, atlasbounds = glyph_data['planeBounds'], glyph_data['atlasBounds']
#             gxpos, gypos = world_x + (planebounds['left'] * font_size), world_y + (planebounds['bottom'] * font_size)
#             gw, gh = (planebounds['right'] - planebounds['left']) * font_size, (
#                         planebounds['top'] - planebounds['bottom']) * font_size
#             u0, v0 = atlasbounds['left'] / atlas_width, atlasbounds['bottom'] / atlas_height
#             u1, v1 = (atlasbounds['right'] - atlasbounds['left']) / atlas_width, (
#                         atlasbounds['top'] - atlasbounds['bottom']) / atlas_height
#             self.pack_into(specific_index, gxpos, gypos, gw, gh, u0, v0, u1, v1,
#                            int(h_low), int(h_high),
#                            reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
#                            pcx, pcy, pcz, int(use_centre))
#
#         p['char_count'] += 1
#
#         if upload_now:
#             global_off = (self.buffer_offset + specific_index) * _STRUCT_SIZE
#             glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
#             glBufferSubData(GL_SHADER_STORAGE_BUFFER, global_off, _STRUCT_SIZE,
#                             memoryview(self.cpu_buffer)[
#                                 specific_index * _STRUCT_SIZE: (specific_index + 1) * _STRUCT_SIZE])
#
#         return advance
#
#     ############################################################################## below this line code needs to be read
#     def _update_layer(self, dt):
#         # anything revealed means the structure of the sentence has changed in any way
#         changed_sentence = False
#         for idx, p in enumerate(self.paragraphs):
#             # skip if all haracters have been processed
#             if not p['pending_char_queue']:
#                 continue
#
#             p['timer'] += dt
#             # if time passed since the sentence was requested to show is bigger or equal
#             # to the interval of time required to display the next part of the sentence
#             if p['timer'] >= p['interval']:
#
#                 # calculate how many reveals you need to show on next gpu update
#                 reveals = int(p['timer'] // p['interval'])
#                 # and remove "interval" amount from "timer" until timer is less than interval
#                 p['timer'] %= p['interval']
#
#                 # for as many reveals as are due
#                 for reveal in range(reveals):
#                     # failsafe in case this runs despite the fact that there are no characters left to process
#                     if not p['pending_char_queue']:
#                         break
#
#                     first_item = p['pending_char_queue'][0]
#
#                     # if the reveal is actually a deletion
#                     if isinstance(first_item, tuple) and first_item[0] == ERASE_ACTION:
#                         cmd = p['pending_char_queue'].pop(0)
#                         self._zero_ssbo_slot(cmd[1])
#                         changed_sentence = True
#
#                     # if the reveal is meant to display words
#                     else:
#                         if p['mode'] == PER_WORD:
#                             current_reveal_id = first_item[6]  # 6 is reveal ID
#                             while p['pending_char_queue']:
#                                 next_item = p['pending_char_queue'][0]
#                                 if isinstance(next_item, tuple) and next_item[0] != ERASE_ACTION and next_item[
#                                     6] == current_reveal_id:
#                                     cmd = p['pending_char_queue'].pop(0)
#                                     self._process_char_to_gpu(idx, *cmd, upload_now=False)
#                                     changed_sentence = True
#                                 else:
#                                     break
#                         else:
#                             cmd = p['pending_char_queue'].pop(0)
#                             self._process_char_to_gpu(idx, *cmd, upload_now=False)
#                             changed_sentence = True
#
#         if changed_sentence:
#             self.update_gpu()
#
#     def update_gpu(self):
#         glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
#         glBufferSubData(GL_SHADER_STORAGE_BUFFER, self.buffer_offset * _STRUCT_SIZE,
#                         self.next_char_index * _STRUCT_SIZE,
#                         bytes(self.cpu_buffer[:self.next_char_index * _STRUCT_SIZE]))
#         glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
#
#     def _offset_paragraph_data(self, p_idx, dx, dy):
#         """Moves both the characters already on GPU and those waiting in the typewriter queue."""
#         p = self.paragraphs[p_idx]
#
#         for i in range(p['char_count']):
#             off = (p['start_char_index'] + i) * _STRUCT_SIZE
#             rect = list(struct.unpack_from('<4f', self.cpu_buffer, off))
#             struct.pack_into('<2f', self.cpu_buffer, off, rect[0] + dx, rect[1] + dy)
#
#         if p['pending_char_queue']:
#             new_queue = []
#             for item in p['pending_char_queue']:
#                 l = list(item)
#                 l[3] += dx
#                 l[4] += dy
#                 new_queue.append(tuple(l))
#             p['pending_char_queue'] = new_queue
#
#         self.update_gpu()
#
#     def calculate_word_width(self, word, font_size, font_key):
#         """adds the advance (multiplied by the font size) of all viable characters in a word"""
#         return sum(self.get_glyph_data(c, font_key).get('advance', 0) * font_size for c in word if
#                    self.get_glyph_data(c, font_key))
#
#     def get_glyph_data(self, char, font_key):
#         # returns glyph data by turning char into its unicode value and using it as a key in the font glyph dictionary
#         return TextHandler.fonts.get(font_key, {}).get('glyphs', {}).get(ord(char))
#
#     def set_paragraph_text(self, p_idx, text, x=None, y=None, z=None, font_size=None,
#                            font_bold_italic_tuple=None, mode=INSTANT_TEXT, interval=None):
#         if p_idx >= len(self.paragraphs): return False
#         p = self.paragraphs[p_idx]
#         target_x = x if x is not None else p['typing_x_start']
#         target_y = y if y is not None else p['typing_y_start']
#         target_z = z if z is not None else p['typing_z_start']
#         f_size = font_size if font_size is not None else p.get('last_font_size', 64)
#         f_key = font_bold_italic_tuple if font_bold_italic_tuple is not None else p.get('last_font_key',
#                                                                                         ("Arial", False, False))
#         for i in range(p['total_char_reserved']):
#             self._zero_ssbo_slot(p['start_char_index'] + i)
#         p['current_text'] = ""
#         p['total_char_reserved'] = 0
#         p['char_count'] = 0
#         p['pending_char_queue'] = []
#         return self.add_text_to_paragraph(
#             p_idx,
#             text,
#             x=target_x,
#             y=target_y,
#             z=target_z,
#             font_size=f_size,
#             font_bold_italic_tuple=f_key,
#             mode=mode,
#             interval=interval
#         )
#
#     def delete_paragraph(self, p_idx):
#         """
#         Zeros out the paragraph's buffer space and deactivates it.
#         This does not 'defragment' the buffer, it just clears the slots.
#         """
#         if p_idx >= len(self.paragraphs):
#             print(f"Warning: Attempted to delete non-existent paragraph index {p_idx}")
#             return False
#         p = self.paragraphs[p_idx]
#         for i in range(p['total_char_reserved']):
#             char_idx = p['start_char_index'] + i
#             self.pack_into(char_idx, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
#                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
#         p['char_count'] = 0
#         p['total_char_reserved'] = 0
#         p['pending_char_queue'] = []
#         p['timer'] = 0.0
#         self.update_gpu()
#         return True
#
#     def optimize_layer(self):  # TODO find a way to call this every so often automatically
#         """
#         Slides all active paragraphs to the beginning of the buffer to reclaim
#         space from deleted paragraphs.
#         """
#         new_next_char_index = 0
#         sorted_paragraphs = sorted(
#             [p for p in self.paragraphs if p['total_char_reserved'] > 0],
#             key=lambda x: x['start_char_index']
#         )
#         for p in sorted_paragraphs:
#             old_start = p['start_char_index']
#             new_start = new_next_char_index
#             if old_start != new_start:
#                 data_size = p['total_char_reserved'] * _STRUCT_SIZE
#                 old_byte_off = old_start * _STRUCT_SIZE
#                 new_byte_off = new_start * _STRUCT_SIZE
#                 self.cpu_buffer[new_byte_off: new_byte_off + data_size] = \
#                     self.cpu_buffer[old_byte_off: old_byte_off + data_size]
#                 p['start_char_index'] = new_start
#                 if p['pending_char_queue']:
#                     new_queue = []
#                     for item in p['pending_char_queue']:
#                         l = list(item)
#                         offset_within_p = l[8] - old_start
#                         l[8] = new_start + offset_within_p
#                         new_queue.append(tuple(l))
#                     p['pending_char_queue'] = new_queue
#             new_next_char_index += p['total_char_reserved']
#         remaining_slots = self.available_characters - new_next_char_index
#         if remaining_slots > 0:
#             off = new_next_char_index * _STRUCT_SIZE
#             self.cpu_buffer[off:] = b'\x00' * (remaining_slots * _STRUCT_SIZE)
#         self.next_char_index = new_next_char_index
#         self.update_gpu()
#
#     def add_text_to_paragraph(self, p_idx, text, x=USE_OWN, y=USE_OWN, z=USE_OWN,
#                               font_size=USE_OWN, font_bold_italic_tuple=USE_OWN,
#                               mode=USE_OWN, interval=USE_OWN,
#                               pitch=0.0, yaw=0.0, roll=0.0,
#                               red=1.0, green=1.0, blue=1.0, alpha=1.0):
#         if p_idx >= len(self.paragraphs):
#             return False
#         p = self.paragraphs[p_idx]
#         f_size = font_size if font_size != USE_OWN else p.get('last_font_size', 64)
#         f_key = font_bold_italic_tuple if font_bold_italic_tuple != USE_OWN else p.get('last_font_key',
#                                                                                        ("Arial", False, False))
#         p_mode = mode if mode != USE_OWN else p['mode']
#         p_interval = interval if interval != USE_OWN else p['interval']
#         if x != USE_OWN: p['typing_x_start'] = x
#         if y != USE_OWN: p['typing_y_start'] = y
#         if z != USE_OWN: p['typing_z_start'] = z
#         p['pitch'], p['yaw'], p['roll'] = pitch, yaw, roll
#         p['r'], p['g'], p['b'], p['a'] = red, green, blue, alpha
#         current_shadow_list = list(p.get('current_text', ""))
#         if x != USE_OWN or y != USE_OWN:
#             typing_x = p['typing_x_start']
#             typing_y = p['typing_y_start']
#         else:
#             typing_x = p.get('last_typing_x', p['typing_x_start'])
#             typing_y = p.get('last_typing_y', p['typing_y_start'])
#         current_z = p['typing_z_start']
#         reveal_id = float(p['total_char_reserved'])
#         word_id = p.get('last_word_id', 0.0)
#         max_len = p['max_paragraph_length']
#         new_prepared = []
#         lines = text.split('\n')
#         for l_idx, line in enumerate(lines):
#             words = line.split(' ')
#             for i, word in enumerate(words):
#                 if not word and i != 0:
#                     continue
#                 w_width = self.calculate_word_width(word, f_size, f_key)
#                 if typing_x + w_width > p['typing_x_start'] + max_len:
#                     typing_x = p['typing_x_start']
#                     typing_y -= (f_size * 1.2)
#                 for char in word:
#                     char_idx = p['start_char_index'] + p['total_char_reserved']
#
#                     new_prepared.append((char, f_key, f_size, typing_x, typing_y, current_z,
#                                          reveal_id, word_id, pitch, yaw, roll,
#                                          red, green, blue, alpha, char_idx))
#
#                     current_shadow_list.append(char)
#                     typing_x += self.calculate_word_width(char, f_size, f_key)
#                     p['total_char_reserved'] += 1
#                     self.next_char_index = max(self.next_char_index, char_idx + 1)
#
#                     if p_mode == PER_LETTER:
#                         reveal_id += 1.0
#                 if i < len(words) - 1:
#                     char_idx = p['start_char_index'] + p['total_char_reserved']
#                     new_prepared.append((' ', f_key, f_size, typing_x, typing_y, current_z,
#                                          reveal_id, word_id, pitch, yaw, roll,
#                                          red, green, blue, alpha, char_idx))
#
#                     current_shadow_list.append(' ')
#                     typing_x += self.calculate_word_width(' ', f_size, f_key)
#                     p['total_char_reserved'] += 1
#                     self.next_char_index = max(self.next_char_index, char_idx + 1)
#
#                     if p_mode == PER_LETTER:
#                         reveal_id += 1.0
#
#                 if p_mode == PER_WORD:
#                     reveal_id += 1.0
#
#                 word_id += 1.0
#             if l_idx < len(lines) - 1:
#                 current_shadow_list.append('\n')
#                 word_id += 1.0
#                 typing_x = p['typing_x_start']
#                 typing_y -= (f_size * 1.2)
#         p['current_text'] = "".join(current_shadow_list)
#         p['last_typing_x'] = typing_x
#         p['last_typing_y'] = typing_y
#         p['last_word_id'] = word_id
#         p['last_font_size'] = f_size
#         p['last_font_key'] = f_key
#         p['mode'] = p_mode
#         p['interval'] = p_interval
#         p['centre_x'] = (p['typing_x_start'] + typing_x) / 2.0
#         p['centre_y'] = (p['typing_y_start'] + typing_y) / 2.0
#         if p_mode == INSTANT_TEXT:
#             for args in new_prepared:
#                 self._process_char_to_gpu(p_idx, *args, upload_now=False)
#             self.update_gpu()
#         else:
#             p['pending_char_queue'].extend(new_prepared)
#
#         return True
#
#     def delete_text_from_paragraph(self, p_idx, target, which_instance=FIRST_INSTANCE_WORD, mode=INSTANT_TEXT,
#                                    interval=0.05):
#         """
#         Deletes the 'target' word from the paragraph.
#         """
#         if p_idx >= len(self.paragraphs):
#             return False
#
#         p = self.paragraphs[p_idx]
#         text = p.get('current_text', "")
#         if not text or not target:
#             return False
#
#         import re
#         target_str = str(target)
#         pattern = rf"\b{re.escape(target_str)}\b"
#         matches = list(re.finditer(pattern, text))
#
#         if not matches:
#             return False
#
#         if which_instance == FIRST_INSTANCE_WORD:
#             target_matches = [matches[0]]
#         elif which_instance == LAST_INSTANCE_WORD:
#             target_matches = [matches[-1]]
#         else:
#             target_matches = matches
#
#         text_list = list(text)
#         erasure_slots = []
#
#         for match in target_matches:
#             s_start, s_end = match.start(), match.end()
#             for i in range(s_start, s_end):
#                 ssbo_idx = p['start_char_index'] + i
#                 erasure_slots.append(ssbo_idx)
#                 text_list[i] = " "
#                 if p['pending_char_queue']:
#                     p['pending_char_queue'] = [
#                         q for q in p['pending_char_queue']
#                         if not (isinstance(q, tuple) and len(q) == 9 and q[8] == ssbo_idx)
#                     ]
#         if mode == INSTANT_TEXT:
#             for slot in erasure_slots:
#                 self._zero_ssbo_slot(slot)
#             self.update_gpu()
#         else:
#             for slot in erasure_slots:
#                 p['pending_char_queue'].append((ERASE_ACTION, slot))
#             p['mode'] = mode
#             p['interval'] = interval
#         p['current_text'] = "".join(text_list)
#         return True
#
#     def _zero_ssbo_slot(self, ssbo_idx):
#         self.pack_into(ssbo_idx,
#                        0.0, 0.0, 0.0, 0.0,
#                        0.0, 0.0, 0.0, 0.0,
#                        0, 0,
#                        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
#
#     def set_paragraph_rotation(self, p_idx, pitch=USE_OWN, yaw=USE_OWN, roll=USE_OWN, use_centre_pivot=USE_OWN):
#         if p_idx >= len(self.paragraphs): return
#         p = self.paragraphs[p_idx]
#         if pitch is not USE_OWN: p['pitch'] = pitch
#         if yaw is not USE_OWN: p['yaw'] = yaw
#         if roll is not USE_OWN: p['roll'] = roll
#         if use_centre_pivot is not USE_OWN: p['use_centre_pivot'] = use_centre_pivot
#         pivot_val = 1 if p['use_centre_pivot'] else 0
#         for i in range(p['char_count']):
#             char_idx = p['start_char_index'] + i
#             off = char_idx * _STRUCT_SIZE
#             struct.pack_into('<I', self.cpu_buffer, off + 8, pivot_val)
#             struct.pack_into('<3f', self.cpu_buffer, off + 56, p['pitch'], p['yaw'], p['roll'])
#             struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], p['typing_z_start'])
#         self.update_gpu()
#
#     def set_paragraph_color(self, p_idx, r=USE_OWN, g=USE_OWN, b=USE_OWN, a=USE_OWN):
#         if p_idx >= len(self.paragraphs): return
#         p = self.paragraphs[p_idx]
#         for i in range(p['char_count']):
#             char_idx = p['start_char_index'] + i
#             off = char_idx * _STRUCT_SIZE
#             color_off = off + (17 * 4)
#             current_rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)
#             new_r = r if r is not USE_OWN else current_rgba[0]
#             new_g = g if g is not USE_OWN else current_rgba[1]
#             new_b = b if b is not USE_OWN else current_rgba[2]
#             new_a = a if a is not USE_OWN else current_rgba[3]
#
#             struct.pack_into('<4f', self.cpu_buffer, color_off, new_r, new_g, new_b, new_a)
#
#         self.update_gpu()
#
#     def get_paragraph_color(self, p_idx):
#         """
#         Returns the RGBA color of the first character in the paragraph.
#         """
#         if p_idx >= len(self.paragraphs):
#             return None
#
#         p = self.paragraphs[p_idx]
#         if p['char_count'] == 0:
#             return (p['r'], p['g'], p['b'], p['a'])  # Return metadata defaults if no chars exist
#
#         char_idx = p['start_char_index']
#         off = char_idx * _STRUCT_SIZE
#         color_off = off + (17 * 4)
#         rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)
#
#         return rgba
#
#     def set_paragraph_position(self, p_idx, x=USE_OWN, y=USE_OWN, z=USE_OWN):
#         """
#         Updates the paragraph's world position by calculating the delta
#         from its current starting coordinates.
#         """
#         if p_idx >= len(self.paragraphs):
#             return False
#
#         p = self.paragraphs[p_idx]
#         target_x = x if x is not USE_OWN else p['typing_x_start']
#         target_y = y if y is not USE_OWN else p['typing_y_start']
#         target_z = z if z is not USE_OWN else p['typing_z_start']
#         dx = target_x - p['typing_x_start']
#         dy = target_y - p['typing_y_start']
#         dz = target_z - p['typing_z_start']
#         p['typing_x_start'] = target_x
#         p['typing_y_start'] = target_y
#         p['typing_z_start'] = target_z
#         p['centre_x'] += dx
#         p['centre_y'] += dy
#         if 'last_typing_x' in p:
#             p['last_typing_x'] += dx
#             p['last_typing_y'] += dy
#         for i in range(p['char_count']):
#             char_idx = p['start_char_index'] + i
#             off = char_idx * _STRUCT_SIZE
#             rect = list(struct.unpack_from('<2f', self.cpu_buffer, off + 12))
#             current_z = struct.unpack_from('<f', self.cpu_buffer, off + 52)[0]
#             struct.pack_into('<2f', self.cpu_buffer, off + 12, rect[0] + dx, rect[1] + dy)
#             struct.pack_into('<f', self.cpu_buffer, off + 52, current_z + dz)
#             struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], target_z)
#         if p['pending_char_queue']:
#             new_queue = []
#             for item in p['pending_char_queue']:
#                 l = list(item)
#                 l[3] += dx  # x
#                 l[4] += dy  # y
#                 l[5] += dz  # z
#                 new_queue.append(tuple(l))
#             p['pending_char_queue'] = new_queue
#         self.update_gpu()
#         return True
#
#     def change_paragraph_position(self, p_idx, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
#         if p_idx >= len(self.paragraphs):
#             return False
#
#         p = self.paragraphs[p_idx]
#         if relative_to == USE_OWN:
#             origin_x = p['typing_x_start']
#             origin_y = p['typing_y_start']
#             origin_z = p['typing_z_start']
#             rot_vec = (p['pitch'], p['yaw'], p['roll'])
#         else:
#             pos = relative_to.get_position()
#             origin_x, origin_y, origin_z = pos[0], pos[1], pos[2]
#             rot_vec = relative_to.get_rotation()
#         if change_vectorially:
#             rot_mat = glm.mat4(1.0)
#             rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[0]), glm.vec3(1, 0, 0))
#             rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[1]), glm.vec3(0, 1, 0))
#             rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[2]), glm.vec3(0, 0, 1))
#
#             direction = glm.vec3(rot_mat * glm.vec4(x, y, z, 0.0))
#             dx, dy, dz = direction.x, direction.y, direction.z
#         else:
#             dx, dy, dz = x, y, z
#         new_x = origin_x + dx
#         new_y = origin_y + dy
#         new_z = origin_z + dz
#         return self.set_paragraph_position(p_idx, x=new_x, y=new_y, z=new_z)
#
#
from OpenGL.GL import *
import json
import os
import subprocess
import struct
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import TextureHandler, UniformHelper, USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
from pyglm import glm
import zipfile

_STRUCT_SIZE = 128
INSTANT_TEXT, PER_LETTER, PER_WORD = "instanttext", "perlettertext", "perwordtext"
ALL_INSTANCES_WORD, FIRST_INSTANCE_WORD, LAST_INSTANCE_WORD = "allinstancestext", "firstinstancetext", "lastinstancetext"
ERASE_ACTION = "ERASE"


class TextHandler:
    initialized = False
    text_shader_storage_buffer = 0
    max_characters = 20000
    fonts = {}
    text_layers = []
    _GLOBAL_TEXT_QUAD = None

    @staticmethod
    def _load_text_handler():
        if not TextHandler.initialized:
            TextHandler.text_shader_storage_buffer = glGenBuffers(1)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
            glBufferData(GL_SHADER_STORAGE_BUFFER, TextHandler.max_characters * _STRUCT_SIZE, None, GL_DYNAMIC_DRAW)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)

            TextHandler._GLOBAL_TEXT_QUAD = Model(None, False, False)
            vertices = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0]
            TextHandler._GLOBAL_TEXT_QUAD.add_vertices(vertices)
            TextHandler._GLOBAL_TEXT_QUAD.connect_vertices([0, 1, 2, 2, 3, 0])

            TextHandler.initialized = True
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

            TextHandler.load_font("Arial")

    @staticmethod
    def load_font(name_of_font, is_bold=False, is_italic=False, font_zip_name=""):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        base_font_dir = os.path.join(project_root, "Layer_0_Modules", "Fonts")
        already_loaded_dir = os.path.join(base_font_dir, "Already_Loaded_Fonts")
        zip_archives_dir = os.path.join(base_font_dir, "Font_Zip_Archives")
        os.makedirs(already_loaded_dir, exist_ok=True)
        generator_exe = os.path.join(current_dir, "msdf-atlas-gen.exe")
        cache_filename = f"atlas_{name_of_font}_{is_bold}_{is_italic}"
        png_filename = f"{cache_filename}.png"
        json_filename = f"{cache_filename}.json"
        cached_png_full = os.path.join(already_loaded_dir, png_filename)
        cached_json_full = os.path.join(already_loaded_dir, json_filename)
        if not (os.path.exists(cached_png_full) and os.path.exists(cached_json_full)):
            print(f"Pregenerated atlas for {name_of_font} not found. Searching zip archives...")
            full_file = None
            extracted_font_path = None

            try:
                for root, dirs, files in os.walk(zip_archives_dir):
                    for file in files:
                        if file.lower().endswith(".zip"):
                            zip_path = os.path.join(root, file)
                            with zipfile.ZipFile(zip_path, 'r') as z:
                                members = z.namelist()
                                if font_zip_name in members:
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

                if not full_file or not os.path.exists(full_file):
                    fallback = os.path.join(base_font_dir, "arial.ttf")
                    full_file = fallback if os.path.exists(fallback) else None

                if not full_file:
                    raise Exception(f"Source '{font_zip_name}' not found as a real file or inside a zip.")

                cmd = [
                    generator_exe, "-font", full_file, "-type", "mtsdf",
                    "-range", "32-255", "-format", "png",
                    "-json", cached_json_full, "-imageout", cached_png_full,
                    "-dimensions", "1024", "1024", "-pxrange", "4", "-edgepadding", "2",
                    "-pot", "-yorigin", "bottom"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Generator error: {result.stderr}")

            except Exception as e:
                raise Exception(f"Critical error generating font {name_of_font}: {e}")
            finally:

                if extracted_font_path and os.path.exists(extracted_font_path):
                    try:
                        os.remove(extracted_font_path)
                    except:
                        pass

        try:
            slot, tex_id = TextureHandler.get_textures(
                png_filename,
                minification_filter=GL_LINEAR,
                magnification_filter=GL_LINEAR,
                file_path=already_loaded_dir,
                generate_mipmap=False,
                return_id_with_slot=True
            )
            actual_handle = TextureHandler.id_handle_dict[tex_id]
            with open(cached_json_full, 'r') as f:
                metadata = json.load(f)

            glyphs_dict = {int(g['unicode']): g for g in metadata['glyphs'] if 'unicode' in g}
            # for each glyph in the (json file's) metadata glyphs, if "unicode" exists in it,glyphs_dict[unicode integer] = glyph

            TextHandler.fonts[(name_of_font, is_bold, is_italic)] = {
                'glyphs': glyphs_dict,
                'texture_handle': actual_handle,
                'atlas_size': (metadata['atlas']['width'], metadata['atlas']['height'])
            }
            return slot
        except Exception as e:
            print(f"Error loading font data for {name_of_font}: {e}")
            return None

    @staticmethod
    def _update(dt):
        for layer in TextHandler.text_layers:
            layer._update_layer(dt)


class TextLayer:
    _total_text_characters = 0

    # TODO remove the arbitrary character limit on everything by dynamically increasing buffers once they get full
    def __init__(self, text_perspective_matrix,
                 available_characters=2000):  # TODO text_perspective_matrix should be camera or perspective matrix
        self.layer_index = len(TextHandler.text_layers)
        if TextLayer._total_text_characters + available_characters > TextHandler.max_characters:
            raise MemoryError(f"SSBO Overflow: Cannot allocate {available_characters} more characters.")

        self.available_characters = available_characters
        self.buffer_offset = TextLayer._total_text_characters
        TextLayer._total_text_characters += available_characters

        TextHandler.text_layers.append(self)
        self.paragraphs = []

        # reserves itself space
        self.cpu_buffer = bytearray(available_characters * _STRUCT_SIZE)

        # index in own buffer
        self.next_char_index = 0

        self._uniform_helper = UniformHelper()
        self._uniform_helper._set_uniforms("text_perspective", text_perspective_matrix)

    def set_text_perspective_matrix(self, new_matrix):
        self._uniform_helper._set_uniforms("text_perspective", new_matrix)

    def get_uniforms(self, names):
        return self._uniform_helper._get_uniforms(names)

    def pack_into(self, struct_size_multiplied_by, gxpos, gypos, gw, gh, u0, v0, u1, v1,
                  h_low, h_high, reveal_id, word_id, abs_z,
                  pitch, yaw, roll, r, g, b, a,
                  pcx, pcy, pcz, use_centre_pivot):
        """This function adds the data of a letter to the cpu buffer"""
        # struct_size_multiplied_by is usually an index integer
        struct.pack_into('<3I29f', self.cpu_buffer, struct_size_multiplied_by * _STRUCT_SIZE,
                         # integers
                         # handles
                         h_low,  # 0
                         h_high,  # 1

                         # rotates around the paragraph or around itself
                         int(use_centre_pivot),  # 2 (0 or 1)

                         # floats

                         # glyph screen position and size
                         gxpos, gypos, gw, gh,  # 3, 4, 5, 6

                         # texture coordinates in atlas
                         u0, v0, u1, v1,  # 7, 8, 9, 10

                         # id used for letter identification in animations
                         reveal_id,  # 11

                         # id used for word identification in animations
                         word_id,  # 12

                         # z coordinate, also used to avoid infighting
                         abs_z,  # 13

                         # rotation angles
                         pitch, yaw, roll,  # 14, 15, 16

                         # color + transparency
                         r, g, b, a,  # 17, 18, 19, 20

                         # paragraph centre
                         pcx, pcy, pcz,  # 21, 22, 23 (Paragraph Centre)

                         # Remaining 8 floats for future bullshit
                         0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                         )

    # TODO add a run system
    def add_new_paragraph(self, text, x=0, y=100, z=0.0, font_size=64, max_paragraph_length=500,
                          font_bold_italic_tuple=("Arial", False, False), mode=INSTANT_TEXT, interval=0.05,
                          pitch=0.0, yaw=0.0, roll=0.0,
                          red=1.0, green=1.0, blue=1.0, alpha=1.0,
                          use_centre_pivot=1):
        """Adds a new paragraph to the text layer."""
        if isinstance(use_centre_pivot, bool):
            if use_centre_pivot:
                use_centre_pivot = 1
            else:
                use_centre_pivot = 0
        else:
            if use_centre_pivot != 1 and use_centre_pivot != 0:
                raise ValueError(
                    f"use_centre_pivot when creating paragraph with text {text} needs to be 0,1 or a boolean")
        # paragraph preparations by setting starting values
        p_idx = len(self.paragraphs)
        start_buffer_index = self.next_char_index
        update_index = self.next_char_index
        p = {
            'typing_x': x, 'typing_y': y, 'typing_z': z,
            'start_char_index': start_buffer_index,
            'char_count': 0, 'total_char_reserved': 0,
            'current_text': text,
            'max_paragraph_length': max_paragraph_length,
            'pending_char_queue': [], 'timer': 0.0, 'interval': interval, 'mode': mode,
            'pitch': pitch, 'yaw': yaw, 'roll': roll,
            'r': red, 'g': green, 'b': blue, 'a': alpha,
            'font_size': font_size, 'font_key': font_bold_italic_tuple,
            'centre_x': x, 'centre_y': y,
            'use_centre_pivot': use_centre_pivot
        }
        self.paragraphs.append(p)
        typing_x, typing_y = x, y
        reveal_id, word_id = 0.0, 0.0
        prepared_chars = []
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')

        # line processing in 2d
        lines = text.split('\n')
        for line in lines:
            words = line.split(' ')
            # word processing
            for i, word in enumerate(words):
                if not word and i != 0: continue

                word_width = self.calculate_word_width(word, font_size, font_bold_italic_tuple)

                # starts writing on the next line (font size*1.2) if the word position+width exceeds the paragraph length
                if typing_x + word_width > x + max_paragraph_length:
                    typing_x, typing_y = x, typing_y - (font_size * 1.2)

                # character processing
                for char in word:
                    char_idx = self.next_char_index
                    char_width = self.calculate_word_width(char, font_size, font_bold_italic_tuple)

                    # calculates paragraph bounds
                    min_x, max_x = min(min_x, typing_x), max(max_x, typing_x + char_width)
                    min_y, max_y = min(min_y, typing_y - (font_size * 1.2)), max(max_y, typing_y)

                    prepared_chars.append((char, font_bold_italic_tuple, font_size, typing_x, typing_y, z,
                                           reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha, char_idx))
                    typing_x += char_width
                    self.next_char_index += 1
                    p['total_char_reserved'] += 1
                    reveal_id += 1.0

                # space character processing
                if i < len(words) - 1:
                    space_width = self.calculate_word_width(' ', font_size, font_bold_italic_tuple)
                    prepared_chars.append((' ', font_bold_italic_tuple, font_size, typing_x, typing_y, z,
                                           reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha,
                                           self.next_char_index))
                    typing_x += space_width
                    self.next_char_index += 1
                    p['total_char_reserved'] += 1
                    reveal_id += 1.0
                    word_id += 1.0
            word_id += 1.0
            # sets the writing to begin from the next line once all words are done on the previous line
            typing_x, typing_y = x, typing_y - (font_size * 1.2)

        # centre coordinate calculation
        if max_x > min_x:
            p['centre_x'], p['centre_y'] = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0

        # if the mode is instant, a request for all the prepared characters to be processed is made immediately.
        # Othersise, they are added to the pending character queue
        if mode == INSTANT_TEXT:
            for args in prepared_chars:
                self._process_char_to_gpu(p_idx, *args, upload_now=False)
            self.update_gpu(update_index, self.next_char_index)
        else:
            p['pending_char_queue'] = prepared_chars

        return p_idx

    def get_font_data(self, font_key):
        return TextHandler.fonts.get(font_key)

    def _process_char_to_gpu(self, p_idx, char, font_key, font_size, world_x, world_y, world_z=0.0,
                             reveal_id=0.0, word_id=0.0, pitch=0.0, yaw=0.0, roll=0.0,
                             r=1.0, g=1.0, b=1.0, a=1.0,
                             specific_index=0, *, upload_now=False):
        """retrieves and formats the necessary data to send to the packing function"""
        p = self.paragraphs[p_idx]

        font_data = self.get_font_data(font_key)
        if not font_data: return 0
        glyph_data = font_data['glyphs'].get(ord(char))
        if not glyph_data: return 0

        pcx = p.get('centre_x', world_x)
        pcy = p.get('centre_y', world_y)
        pcz = p.get('typing_z_start', world_z)
        use_centre = p.get('use_centre_pivot')

        handle = font_data.get('texture_handle', 0)
        atlas_width, atlas_height = font_data['atlas_size']
        advance = glyph_data.get('advance', 0) * font_size

        h_low = (handle & 0xFFFFFFFF)
        h_high = ((handle >> 32) & 0xFFFFFFFF)

        # if no planebounds, send
        if 'planeBounds' not in glyph_data:
            self.pack_into(specific_index, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           int(h_low), int(h_high),
                           reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
                           pcx, pcy, pcz, int(use_centre))
        else:
            planebounds, atlasbounds = glyph_data['planeBounds'], glyph_data['atlasBounds']
            gxpos, gypos = world_x + (planebounds['left'] * font_size), world_y + (planebounds['bottom'] * font_size)
            gw, gh = (planebounds['right'] - planebounds['left']) * font_size, (
                        planebounds['top'] - planebounds['bottom']) * font_size
            u0, v0 = atlasbounds['left'] / atlas_width, atlasbounds['bottom'] / atlas_height
            u1, v1 = (atlasbounds['right'] - atlasbounds['left']) / atlas_width, (
                        atlasbounds['top'] - atlasbounds['bottom']) / atlas_height
            self.pack_into(specific_index, gxpos, gypos, gw, gh, u0, v0, u1, v1,
                           int(h_low), int(h_high),
                           reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
                           pcx, pcy, pcz, int(use_centre))

        p['char_count'] += 1

        if upload_now:
            self.update_gpu(specific_index, specific_index + 1)
        return advance

    def _update_layer(self, dt):
        """dictates how many new words/letters are shown """
        # anything revealed means the structure of the sentence has changed in any way
        changed_sentence = False

        for idx, p in enumerate(self.paragraphs):
            # skip if all haracters have been processed
            if not p['pending_char_queue']:
                continue

            p['timer'] += dt
            # if time passed since the sentence was requested to show is bigger or equal
            # to the interval of time required to display the next part of the sentence
            if p['timer'] >= p['interval']:

                # calculate how many reveals you need to show on next gpu update
                reveals = int(p['timer'] // p['interval'])
                # and remove "interval" amount from "timer" until timer is less than interval
                p['timer'] %= p['interval']

                # for as many reveals as are due
                for reveal in range(reveals):
                    # failsafe in case this runs despite the fact that there are no characters left to process
                    if not p['pending_char_queue']:
                        break

                    first_item = p['pending_char_queue'][0]

                    # if the reveal is actually a deletion
                    if isinstance(first_item, tuple) and first_item[0] == ERASE_ACTION:
                        cmd = p['pending_char_queue'].pop(0)
                        self._zero_ssbo_slot(cmd[1])
                        changed_sentence = True

                    # if the reveal is meant to display words
                    else:
                        if p['mode'] == PER_WORD:
                            current_reveal_id = first_item[7]  # 6 is reveal ID, 7 is word ID
                            # while there's pending characters
                            while p['pending_char_queue']:
                                next_item = p['pending_char_queue'][0]

                                if isinstance(next_item, tuple) and next_item[0] != ERASE_ACTION and next_item[
                                    7] == current_reveal_id:
                                    cmd = p['pending_char_queue'].pop(0)
                                    self._process_char_to_gpu(idx, *cmd, upload_now=False)
                                    changed_sentence = True
                                else:
                                    break
                        else:
                            cmd = p['pending_char_queue'].pop(0)
                            self._process_char_to_gpu(idx, *cmd, upload_now=False)
                            changed_sentence = True

        if changed_sentence:
            self.update_gpu(0, self.next_char_index)

    def update_gpu(self, start_index, end_index):

        """updates a smaller part of the big text buffer"""
        # binding the shader storage buffer as the big text buffer from the text handler
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
        start_offset = (self.buffer_offset + start_index) * _STRUCT_SIZE
        data_size = (end_index - start_index) * _STRUCT_SIZE
        slice_start = start_index * _STRUCT_SIZE
        slice_end = end_index * _STRUCT_SIZE
        raw_data = bytes(self.cpu_buffer[slice_start:slice_end])
        glBufferSubData(GL_SHADER_STORAGE_BUFFER, start_offset, data_size, raw_data)

        glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    # def _offset_paragraph_data(self, p_idx, dx, dy):
    #     """Moves both the characters already on GPU and those waiting in the typewriter queue."""
    #     p = self.paragraphs[p_idx]
    #
    #     for i in range(p['char_count']):
    #         off = (p['start_char_index'] + i) * _STRUCT_SIZE
    #         rect = list(struct.unpack_from('<4f', self.cpu_buffer, off))
    #         struct.pack_into('<2f', self.cpu_buffer, off, rect[0] + dx, rect[1] + dy)
    #
    #
    #     if p['pending_char_queue']:
    #         new_queue = []
    #         for item in p['pending_char_queue']:
    #             l = list(item)
    #             l[3] += dx
    #             l[4] += dy
    #             new_queue.append(tuple(l))
    #         p['pending_char_queue'] = new_queue
    #
    #     self.update_gpu()

    def calculate_word_width(self, word, font_size, font_key):
        """adds the advance (multiplied by the font size) of all viable characters in a word"""
        return sum(self.get_glyph_data(c, font_key).get('advance', 0) * font_size for c in word if
                   self.get_glyph_data(c, font_key))

    def get_glyph_data(self, char, font_key):
        """returns glyph data by turning char into its unicode value and using it as a key in the font glyph dictionary"""
        return TextHandler.fonts.get(font_key, {}).get('glyphs', {}).get(ord(char))

    ############################################################################## below this line code needs to be read
    def clear_paragraph_text(self, paragraph_index):
        """clears text from relevant paragraph"""
        paragraph = self.paragraphs[paragraph_index]
        # zeroes all the reserved characters of the paragraph
        for i in range(paragraph['total_char_reserved']):
            self._zero_ssbo_slot(paragraph['start_char_index'] + i)
        # sets all relevant data
        paragraph['current_text'] = ""
        paragraph['total_char_reserved'] = 0
        paragraph['char_count'] = 0
        paragraph['pending_char_queue'] = []
        return paragraph["start_char_index"],

    def set_paragraph_text(self, p_idx, text, x=USE_OWN, y=USE_OWN, z=USE_OWN, font_size=USE_OWN,
                           font_bold_italic_tuple=USE_OWN, mode=INSTANT_TEXT, interval=None):
        """clears the paragraph (without defragmenting it) and then calls add_text_to_paragraph on the now empty paragraph"""
        if p_idx >= len(self.paragraphs): return False
        p = self.paragraphs[p_idx]
        # sets values
        target_x = x if x is not USE_OWN else p['typing_x_start']
        target_y = y if y is not USE_OWN else p['typing_y_start']
        target_z = z if z is not USE_OWN else p['typing_z_start']
        f_size = font_size if font_size is not USE_OWN else p.get('last_font_size', 64)
        f_key = font_bold_italic_tuple if font_bold_italic_tuple is not USE_OWN else p.get('last_font_key',
                                                                                           ("Arial", False, False))

        self.clear_paragraph_text(p_idx)
        return self.add_text_to_paragraph(
            p_idx,
            text,
            x=target_x,
            y=target_y,
            z=target_z,
            font_size=f_size,
            font_bold_italic_tuple=f_key,
            mode=mode,
            interval=interval
        )

    def delete_paragraph(self, p_idx):
        """
        Zeros out the paragraph's buffer space and deactivates it.
        This does not 'defragment' the buffer, it just clears the slots.
        """
        if p_idx >= len(self.paragraphs):
            print(f"Warning: Attempted to delete non-existent paragraph index {p_idx}")
            return False

        self.update_gpu(*self.clear_paragraph_text(p_idx))
        return True

    def optimize_layer(self):  # TODO find a way to call this every so often automatically
        """
        Slides all active paragraphs to the beginning of the buffer to reclaim
        space from deleted paragraphs.
        """
        new_next_char_index = 0
        sorted_paragraphs = sorted(
            [p for p in self.paragraphs if p['total_char_reserved'] > 0],
            key=lambda x: x['start_char_index']
        )
        for p in sorted_paragraphs:
            old_start = p['start_char_index']
            new_start = new_next_char_index
            if old_start != new_start:
                data_size = p['total_char_reserved'] * _STRUCT_SIZE
                old_byte_off = old_start * _STRUCT_SIZE
                new_byte_off = new_start * _STRUCT_SIZE
                self.cpu_buffer[new_byte_off: new_byte_off + data_size] = \
                    self.cpu_buffer[old_byte_off: old_byte_off + data_size]
                p['start_char_index'] = new_start
                if p['pending_char_queue']:
                    new_queue = []
                    for item in p['pending_char_queue']:
                        l = list(item)
                        offset_within_p = l[8] - old_start
                        l[8] = new_start + offset_within_p
                        new_queue.append(tuple(l))
                    p['pending_char_queue'] = new_queue
            new_next_char_index += p['total_char_reserved']
        remaining_slots = self.available_characters - new_next_char_index
        if remaining_slots > 0:
            off = new_next_char_index * _STRUCT_SIZE
            self.cpu_buffer[off:] = b'\x00' * (remaining_slots * _STRUCT_SIZE)
        self.next_char_index = new_next_char_index
        self.update_gpu()

    def add_text_to_paragraph(self, p_idx, text, x=USE_OWN, y=USE_OWN, z=USE_OWN,
                              font_size=USE_OWN, font_bold_italic_tuple=USE_OWN,
                              mode=USE_OWN, interval=USE_OWN,
                              pitch=0.0, yaw=0.0, roll=0.0,
                              red=1.0, green=1.0, blue=1.0, alpha=1.0):  # TODO remove and redo with runs
        if p_idx >= len(self.paragraphs):
            return False
        p = self.paragraphs[p_idx]
        f_size = font_size if font_size != USE_OWN else p.get('last_font_size', 64)
        f_key = font_bold_italic_tuple if font_bold_italic_tuple != USE_OWN else p.get('last_font_key',
                                                                                       ("Arial", False, False))
        p_mode = mode if mode != USE_OWN else p['mode']
        p_interval = interval if interval != USE_OWN else p['interval']
        if x != USE_OWN: p['typing_x_start'] = x
        if y != USE_OWN: p['typing_y_start'] = y
        if z != USE_OWN: p['typing_z_start'] = z
        p['pitch'], p['yaw'], p['roll'] = pitch, yaw, roll
        p['r'], p['g'], p['b'], p['a'] = red, green, blue, alpha
        current_shadow_list = list(p.get('current_text', ""))
        if x != USE_OWN or y != USE_OWN:
            typing_x = p['typing_x_start']
            typing_y = p['typing_y_start']
        else:
            typing_x = p.get('last_typing_x', p['typing_x_start'])
            typing_y = p.get('last_typing_y', p['typing_y_start'])
        current_z = p['typing_z_start']
        reveal_id = float(p['total_char_reserved'])
        word_id = p.get('last_word_id', 0.0)
        max_len = p['max_paragraph_length']
        new_prepared = []
        lines = text.split('\n')
        for l_idx, line in enumerate(lines):
            words = line.split(' ')
            for i, word in enumerate(words):
                if not word and i != 0:
                    continue
                w_width = self.calculate_word_width(word, f_size, f_key)
                if typing_x + w_width > p['typing_x_start'] + max_len:
                    typing_x = p['typing_x_start']
                    typing_y -= (f_size * 1.2)
                for char in word:
                    char_idx = p['start_char_index'] + p['total_char_reserved']

                    new_prepared.append((char, f_key, f_size, typing_x, typing_y, current_z,
                                         reveal_id, word_id, pitch, yaw, roll,
                                         red, green, blue, alpha, char_idx))

                    current_shadow_list.append(char)
                    typing_x += self.calculate_word_width(char, f_size, f_key)
                    p['total_char_reserved'] += 1
                    self.next_char_index = max(self.next_char_index, char_idx + 1)

                    if p_mode == PER_LETTER:
                        reveal_id += 1.0
                if i < len(words) - 1:
                    char_idx = p['start_char_index'] + p['total_char_reserved']
                    new_prepared.append((' ', f_key, f_size, typing_x, typing_y, current_z,
                                         reveal_id, word_id, pitch, yaw, roll,
                                         red, green, blue, alpha, char_idx))

                    current_shadow_list.append(' ')
                    typing_x += self.calculate_word_width(' ', f_size, f_key)
                    p['total_char_reserved'] += 1
                    self.next_char_index = max(self.next_char_index, char_idx + 1)

                    if p_mode == PER_LETTER:
                        reveal_id += 1.0

                if p_mode == PER_WORD:
                    reveal_id += 1.0

                word_id += 1.0
            if l_idx < len(lines) - 1:
                current_shadow_list.append('\n')
                word_id += 1.0
                typing_x = p['typing_x_start']
                typing_y -= (f_size * 1.2)
        p['current_text'] = "".join(current_shadow_list)
        p['last_typing_x'] = typing_x
        p['last_typing_y'] = typing_y
        p['last_word_id'] = word_id
        p['last_font_size'] = f_size
        p['last_font_key'] = f_key
        p['mode'] = p_mode
        p['interval'] = p_interval
        p['centre_x'] = (p['typing_x_start'] + typing_x) / 2.0
        p['centre_y'] = (p['typing_y_start'] + typing_y) / 2.0
        if p_mode == INSTANT_TEXT:
            for args in new_prepared:
                self._process_char_to_gpu(p_idx, *args, upload_now=False)
            self.update_gpu(0, self.next_char_index)
        else:
            p['pending_char_queue'].extend(new_prepared)

        return True

    def delete_text_from_paragraph(self, p_idx, target, which_instance=FIRST_INSTANCE_WORD, mode=INSTANT_TEXT,
                                   interval=0.05):  # TODO revamp
        """
        Deletes the 'target' word from the paragraph.
        """
        if p_idx >= len(self.paragraphs):
            return False

        p = self.paragraphs[p_idx]
        text = p.get('current_text', "")
        if not text or not target:
            return False

        import re
        target_str = str(target)
        pattern = rf"\b{re.escape(target_str)}\b"
        matches = list(re.finditer(pattern, text))

        if not matches:
            return False

        if which_instance == FIRST_INSTANCE_WORD:
            target_matches = [matches[0]]
        elif which_instance == LAST_INSTANCE_WORD:
            target_matches = [matches[-1]]
        else:
            target_matches = matches

        text_list = list(text)
        erasure_slots = []

        for match in target_matches:
            s_start, s_end = match.start(), match.end()
            for i in range(s_start, s_end):
                ssbo_idx = p['start_char_index'] + i
                erasure_slots.append(ssbo_idx)
                text_list[i] = " "
                if p['pending_char_queue']:
                    p['pending_char_queue'] = [
                        q for q in p['pending_char_queue']
                        if not (isinstance(q, tuple) and len(q) == 9 and q[8] == ssbo_idx)
                    ]
        if mode == INSTANT_TEXT:
            for slot in erasure_slots:
                self._zero_ssbo_slot(slot)
            self.update_gpu(p["start_char_index"], p["total_char_reserved"])
        else:
            for slot in erasure_slots:
                p['pending_char_queue'].append((ERASE_ACTION, slot))
            p['mode'] = mode
            p['interval'] = interval
        p['current_text'] = "".join(text_list)
        return True

    def _zero_ssbo_slot(self, ssbo_idx):
        """sets packs the index offered into full zeroes."""
        self.pack_into(ssbo_idx,
                       0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0,
                       0, 0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

    def set_paragraph_rotation(self, p_idx, pitch=USE_OWN, yaw=USE_OWN, roll=USE_OWN, use_centre_pivot=USE_OWN):
        if p_idx >= len(self.paragraphs): return
        p = self.paragraphs[p_idx]
        if pitch is not USE_OWN: p['pitch'] = pitch
        if yaw is not USE_OWN: p['yaw'] = yaw
        if roll is not USE_OWN: p['roll'] = roll
        if use_centre_pivot is not USE_OWN: p['use_centre_pivot'] = use_centre_pivot
        pivot_val = 1 if p['use_centre_pivot'] else 0
        for i in range(p['char_count']):
            char_idx = p['start_char_index'] + i
            off = char_idx * _STRUCT_SIZE
            struct.pack_into('<I', self.cpu_buffer, off + 8, pivot_val)
            struct.pack_into('<3f', self.cpu_buffer, off + 56, p['pitch'], p['yaw'], p['roll'])
            struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], p['typing_z_start'])
        self.update_gpu(p["start_char_index"], p["total_char_reserved"])

    def set_paragraph_color(self, p_idx, r=USE_OWN, g=USE_OWN, b=USE_OWN, a=USE_OWN):
        if p_idx >= len(self.paragraphs): return
        p = self.paragraphs[p_idx]
        for i in range(p['char_count']):
            char_idx = p['start_char_index'] + i
            off = char_idx * _STRUCT_SIZE
            color_off = off + (17 * 4)
            current_rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)
            new_r = r if r is not USE_OWN else current_rgba[0]
            new_g = g if g is not USE_OWN else current_rgba[1]
            new_b = b if b is not USE_OWN else current_rgba[2]
            new_a = a if a is not USE_OWN else current_rgba[3]

            struct.pack_into('<4f', self.cpu_buffer, color_off, new_r, new_g, new_b, new_a)

        self.update_gpu(p["start_char_index"], p["total_char_reserved"])

    def get_paragraph_color(self, p_idx):
        """
        Returns the RGBA color of the first character in the paragraph.
        """
        if p_idx >= len(self.paragraphs):
            return None

        p = self.paragraphs[p_idx]
        if p['char_count'] == 0:
            return (p['r'], p['g'], p['b'], p['a'])  # Return metadata defaults if no chars exist

        char_idx = p['start_char_index']
        off = char_idx * _STRUCT_SIZE
        color_off = off + (17 * 4)
        rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)

        return rgba

    def set_paragraph_position(self, p_idx, x=USE_OWN, y=USE_OWN, z=USE_OWN):
        """
        Updates the paragraph's world position by calculating the delta
        from its current starting coordinates.
        """
        if p_idx >= len(self.paragraphs):
            return False

        p = self.paragraphs[p_idx]
        target_x = x if x is not USE_OWN else p['typing_x_start']
        target_y = y if y is not USE_OWN else p['typing_y_start']
        target_z = z if z is not USE_OWN else p['typing_z_start']
        dx = target_x - p['typing_x_start']
        dy = target_y - p['typing_y_start']
        dz = target_z - p['typing_z_start']
        p['typing_x_start'] = target_x
        p['typing_y_start'] = target_y
        p['typing_z_start'] = target_z
        p['centre_x'] += dx
        p['centre_y'] += dy
        if 'last_typing_x' in p:
            p['last_typing_x'] += dx
            p['last_typing_y'] += dy
        for i in range(p['char_count']):
            char_idx = p['start_char_index'] + i
            off = char_idx * _STRUCT_SIZE
            rect = list(struct.unpack_from('<2f', self.cpu_buffer, off + 12))
            current_z = struct.unpack_from('<f', self.cpu_buffer, off + 52)[0]
            struct.pack_into('<2f', self.cpu_buffer, off + 12, rect[0] + dx, rect[1] + dy)
            struct.pack_into('<f', self.cpu_buffer, off + 52, current_z + dz)
            struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], target_z)
        if p['pending_char_queue']:
            new_queue = []
            for item in p['pending_char_queue']:
                l = list(item)
                l[3] += dx  # x
                l[4] += dy  # y
                l[5] += dz  # z
                new_queue.append(tuple(l))
            p['pending_char_queue'] = new_queue
        self.update_gpu()
        return True

    def change_paragraph_position(self, p_idx, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
        if p_idx >= len(self.paragraphs):
            return False

        p = self.paragraphs[p_idx]
        if relative_to == USE_OWN:
            origin_x = p['typing_x_start']
            origin_y = p['typing_y_start']
            origin_z = p['typing_z_start']
            rot_vec = (p['pitch'], p['yaw'], p['roll'])
        else:
            pos = relative_to.get_position()
            origin_x, origin_y, origin_z = pos[0], pos[1], pos[2]
            rot_vec = relative_to.get_rotation()
        if change_vectorially:
            rot_mat = glm.mat4(1.0)
            rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[0]), glm.vec3(1, 0, 0))
            rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[1]), glm.vec3(0, 1, 0))
            rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[2]), glm.vec3(0, 0, 1))

            direction = glm.vec3(rot_mat * glm.vec4(x, y, z, 0.0))
            dx, dy, dz = direction.x, direction.y, direction.z
        else:
            dx, dy, dz = x, y, z
        new_x = origin_x + dx
        new_y = origin_y + dy
        new_z = origin_z + dz
        return self.set_paragraph_position(p_idx, x=new_x, y=new_y, z=new_z)

