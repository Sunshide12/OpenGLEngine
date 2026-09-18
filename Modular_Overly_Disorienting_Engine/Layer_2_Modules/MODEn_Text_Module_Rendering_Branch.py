import re
import glfw
from OpenGL.GL import *
import json
import os
import subprocess
import struct
from Modular_Overly_Disorienting_Engine import TimeHandler
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import TextureHandler,UniformHelper,USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
from enum import Enum
import zipfile

#TODO
# HANDLER has the big gpu + cpu
# THE LAYERS have parts of the cpu
# THE PARAGRAPHS have no memory
# THE SENTENCES have no memory pools of their own but
# act as the writing agents that request a destination index from the layer,
# pack raw character structs directly into that layer's cpu buffer slice,
# and track internal text lengths to trigger global handler expansions
# or layer-wide repacks when capacity thresholds break

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

class TextHandler:
    initialized = False
    text_shader_storage_buffer = 0
    _max_characters = 8192
    fonts = {}
    text_layers = []
    _GLOBAL_TEXT_QUAD = None
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
            #for each glyph in the (json file's) metadata glyphs, if "unicode" exists in it,glyphs_dict[unicode integer] = glyph

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
    """A text layer is a collection of paragraph with common characteristics.
       Likewise, it is responsible with updating the paragraphs with information regarding time"""
    _total_reserved_characters=0
    def __init__(self,perspective_matrix):  #TODO text_perspective_matrix should be camera or perspective matrix
        """Pack_into packs and moves individual letters into the CPU buffer
                   Update_gpu replaces the layer's portion of the data in the GPU SSBO with its new CPU buffer"""
        #offers itself an index
        self.layer_index = len(TextHandler.text_layers)
        self.buffer_offset = TextLayer._total_reserved_characters
        TextLayer._total_reserved_characters+=2048
        #recreates the global SSBO, doubles its size and transfers all the data
        #this runs if the total characters reserved so far + the ones from the newly made layer > the max characters the handler supports
        if TextLayer._total_reserved_characters >= TextHandler._max_characters: #TODO  actually fucking make work
        #     self.optimize_layer()                 #TODO
        #     old_char_limit = TextHandler.max_characters
        #     TextHandler.max_characters = old_char_limit * 2
        #     old_byte_size = old_char_limit * _STRUCT_SIZE
        #     new_byte_size = TextHandler.max_characters * _STRUCT_SIZE
        #     new_ssbo = glGenBuffers(1)
        #     glBindBuffer(GL_COPY_WRITE_BUFFER, new_ssbo)
        #     glBufferData(GL_COPY_WRITE_BUFFER, new_byte_size, None, GL_DYNAMIC_DRAW)
        #     glBindBuffer(GL_COPY_READ_BUFFER, TextHandler.text_shader_storage_buffer)
        #     glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER, 0, 0, old_byte_size)
        #     glDeleteBuffers(1, TextHandler.text_shader_storage_buffer)
        #     TextHandler.text_shader_storage_buffer = new_ssbo
        #     glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, TextHandler.text_shader_storage_buffer)
        #     glBindBuffer(GL_COPY_READ_BUFFER, 0)
        #     glBindBuffer(GL_COPY_WRITE_BUFFER, 0)
            TextHandler._double_space()
            self.optimize_layer()

        self.reserved_characters = 2048
        self.free_memory_blocks=list(range(self.reserved_characters//MEMORY_BLOCK_SIZE))
        # its offset in the global SSBO (the first empty space after all previously reserved space by other layers)
        TextHandler.text_layers.append(self)
        self.paragraphs = []

        #reserves itself space on the CPU side.
        #the CPU side is worked on, and the GPU side is only asked to render the already curated data.
        self.cpu_buffer = bytearray(self.reserved_characters * _STRUCT_SIZE)

        #next character's index out of all available characters
        self.last_char_index = 0

        #the standard MODEn uniform helper
        self._uniform_helper=UniformHelper()
        self._uniform_helper._set_uniforms("text_perspective",perspective_matrix)


    def set_text_perspective_matrix(self,new_matrix):
        self._uniform_helper._set_uniforms("text_perspective", new_matrix)
    def get_uniforms(self,names):
        return self._uniform_helper._get_uniforms(names)
    def _pack_into(self, index_in_buffer,h_low, h_high, use_centre_pivot, gxpos, gypos, gw, gh, u0, v0, u1, v1,
                   reveal_id, word_id, abs_z,
                  pitch, yaw, roll, r, g, b, a,
                  pcx, pcy, pcz, ):
        """This function adds the data of a letter to the cpu buffer"""
        struct.pack_into('<3I29f', self.cpu_buffer, index_in_buffer * _STRUCT_SIZE,
                         # integers
                         # handles
                         h_low,  # 0
                         h_high,  # 1

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

    def _update_gpu(self,start_index,end_index):
        """Updates a smaller part of the big GPU SSBO
           Uses a slice (from start_index*struct_size to end_index*struct_size) of the CPU buffer"""
        #binding the shader storage buffer as the big text buffer from the text handler
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
        start_offset = (self.buffer_offset + start_index) * _STRUCT_SIZE
        data_size = (end_index - start_index) * _STRUCT_SIZE
        slice_start = start_index * _STRUCT_SIZE
        slice_end = end_index * _STRUCT_SIZE
        raw_data = bytes(self.cpu_buffer[slice_start:slice_end])
        glBufferSubData(GL_SHADER_STORAGE_BUFFER, start_offset, data_size, raw_data)


        glBindBuffer(GL_SHADER_STORAGE_BUFFER,0)
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
    def _calculate_memory_block_quantity(self):
        return self.reserved_characters//MEMORY_BLOCK_SIZE
    def _offer_memory_block(self):

        if len(self.free_memory_blocks)==0:
            old_block_count = self._calculate_memory_block_quantity()
            self._double_reserved_characters()
            new_block_count = self._calculate_memory_block_quantity()
            new_blocks = list(range(old_block_count, new_block_count))
            self.free_memory_blocks.extend(new_blocks)
        return self.free_memory_blocks.pop(0)


class Paragraph:
    """
        Paragraphs are a collection of sentences
        A paragraph is responsible with sharing where (globally) and when(globally) , a sentence is meant and allowed to display,
    """
    __slots__=["_sentences","_packets_to_process","_unfinished_sentence_indexes","_layer","_x","_y","_z","_width","_height","_depth","_is_position_centre"]
    def __init__(self,layer):
        self._sentences=[]
        self._unfinished_sentence_indexes=[]
        self._layer=layer
        self._x=0
        self._y=0
        self._z=0
        self._width=-1
        self._height=-1
        self._depth=-1
        self._is_position_centre = False
        self._packets_to_process=[]
    def add_sentence(self,text:str,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05,delay_mode=DELAY_WAIT_FOR_SENTENCE,delay_target=None,return_index_instead_of_object:bool=False):
        """Adds a sentence to the paragraph. A sentence is a collection of runs
           A paragraph can house as many sentences as it needs to, but a sentence cannot exist without belonging to a paragraph"""
        new_sentence=Sentence(self)
        self._unfinished_sentence_indexes.append(len(self._sentences))
        self._sentences.append(new_sentence)
        new_sentence.set_delay(delay_mode,delay_target)
        new_sentence.add_text(text,font_key,size,r,g,b,a,mode,interval_in_seconds,)
        if not return_index_instead_of_object:
            return new_sentence
        else:
            return len(self._sentences)
    def update(self,dt):
        if len(self._unfinished_sentence_indexes) > 0: #TODO might be able to optimize further?
            for sentence_index in self._unfinished_sentence_indexes:
                self._sentences[sentence_index].update(dt,sentence_index)
            self._process_packets()
    def request_memory_block(self):
        return self._layer._offer_memory_block()
    def _receive_sentence_packet_for_processing(self,packet):
        self._packets_to_process.append(packet)
    def _process_packets(self):
        if self._packets_to_process:
            for packet in self._packets_to_process:
                pass
class Sentence:
    """Hold an ordered collection of runs
       The sentence is responsible with knowing what , where(relative to the paragraph),
       and when (relative to the paragraph) it is meant to display."""
    __slots__=["memory_blocks","internal_timer","last_used_run_remaining_characters","last_used_run_index","text","paragraph","pending_text","runs","x","y","z","pitch","yaw","roll","boundary_x","boundary_y","boundary_z","delay_mode","delay_target","delay_achieved","paused","is_position_centre","rotate_sentence_around_paragraph","rotate_letters_around_sentence"]
    def __init__(self,paragraph):
        self.memory_blocks=[]
        self.text=""
        self.paragraph=paragraph
        self.pending_text=""
        self.runs=[]
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
        self.request_memory_block()
        self.last_used_run_index=None
        self.last_used_run_remaining_characters=0
        self.internal_timer=0
    def signal_delay_completion(self):
        self.delay_achieved=True
    def set_delay(self,mode=USE_OWN,target=USE_OWN,achieved:bool=USE_OWN):
        if mode != USE_OWN:
            self.delay_mode=mode
        if target != USE_OWN:
            if mode == DELAY_WAIT_FOR_TIME:
                self.delay_target=TimeHandler.set_timed_function(self.signal_delay_completion,target,True,False)
        if achieved != USE_OWN:
            self.delay_achieved=achieved
    def _add_run(self,length,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05,return_index_instead_of_object:bool=False):
        """Adds a text run to the sentence. A text run is a collection of similar bits of raw data.
           A sentence can house as many text runs as it needs to, but a text run cannot exist without belonging to a sentence"""
        new_run=TextRun(length,len(self.text)-length,font_key,size, r, g, b, a, mode, interval_in_seconds)
        self.runs.append(new_run)
        if not return_index_instead_of_object:
            return new_run
        else:
            return len(self.runs)
    def check_if_same_run(self):
        pass
    def request_memory_block(self):
        self.memory_blocks.append(self.paragraph.request_memory_block())


    def add_text(self,text,font_key=FONT_KEY_DEFAULT,size=0.05,r=1.0,g=1.0,b=1.0,a=1.0,mode=MODE_INSTANT_TEXT,interval_in_seconds=0.05):
        length_of_added_text=len(text)
        last_run_index = len(self.runs) - 1
        self.pending_text+=text
        extra_blocks_needed=(len(self.text) + MEMORY_BLOCK_SIZE - 1) // MEMORY_BLOCK_SIZE-len(self.memory_blocks)
        if extra_blocks_needed>0:
            for i in range(extra_blocks_needed):
                self.request_memory_block()
        if last_run_index != -1:
            last_run = self.runs[last_run_index]
            data = last_run._get_all_info()
            #this runs in order to extend the last run if the current run's settings are identical, thus reducing their count
            matching_features=0
            new_text_data=[size, font_key, r, g, b, a, mode, interval_in_seconds, ]
            # checks every feature except length and offset

            for index,name_of_data in enumerate(data):
                if name_of_data != "length" and name_of_data != "offset":
                    if data[name_of_data] == new_text_data[index-2]:
                        matching_features+=1


            #this runs if all of the relevant qualities match
            if matching_features == 8:
                #extends the length of the last run
                last_run._change_length(length_of_added_text)
                return last_run
            else:
                run_to_return=self._add_run(len(text),font_key,size, r, g, b, a, mode, interval_in_seconds)

        else:
            run_to_return=self._add_run(len(text),font_key,size, r, g, b, a, mode, interval_in_seconds)

        if self.last_used_run_index is None:
            self.last_used_run_index=last_run_index
            self.last_used_run_remaining_characters=self.runs[self.last_used_run_index].length
        return run_to_return
    def _get_substring(self,regex_string,ignore_upper_lower_case:bool=True):
        if ignore_upper_lower_case:
            return re.findall(regex_string,self.text,re.IGNORECASE)
        else:
            return re.findall(regex_string, self.text)
    def _erase_text(self,regex_string,instance):
        self._get_substring(regex_string) #TODO complete
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
                        if self.paragraph._sentences[target_index].pending_text=="":
                            self.delay_achieved=True
                    else:
                        #This branch makes sure that a sentence which has SENTENCE_PREVIOUS as it's mode
                        #while also being the first in the paragraph
                        #is immediately marked as able to be processed because it must wait for none
                        self.delay_achieved=True

                elif isinstance(target_sentence,Sentence):
                    #The specific sentence by instance
                    if target_sentence.pending_text=="":
                        self.delay_achieved=True
                else:
                    #The specific sentence by index
                    if self.paragraph._sentences[target_sentence].pending_text=="":
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
        TimeHandler.pause_function(self.signal_delay_completion)
    def unpause(self):
        TimeHandler.unpause_function(self.signal_delay_completion)
    def toggle_pause(self):
        TimeHandler.toggle_pause(self.signal_delay_completion)
    def update(self,dt,sentence_index):  #TODO change and improve

        if not self.paused:
            if not self.delay_achieved:
                self.check_delay_achievement(sentence_index)
            if self.delay_achieved:
                if self.pending_text:
                    sufficient_timer_for_reveals=True
                    self.internal_timer += dt
                    while sufficient_timer_for_reveals:
                        run_length,run_mode,run_interval=self.runs[self.last_used_run_index]._get_update_data()
                        # if run_mode != MODE_INSTANT_TEXT:
                        reveals=int(min(self.internal_timer//run_interval,self.last_used_run_remaining_characters))
                        self.internal_timer-=reveals*run_interval
                        self.last_used_run_remaining_characters-=reveals
                        characters_to_process=self.pending_text[:reveals]
                        self.pending_text=self.pending_text[reveals:]
                        if characters_to_process:
                            self._send_packet_for_processing(characters_to_process,len(self.text),self.runs[self.last_used_run_index])
                            self.text+=characters_to_process
                        if self.last_used_run_remaining_characters <=0 and self.last_used_run_index+1<len(self.runs):
                            self.last_used_run_index+=1
                            self.last_used_run_remaining_characters=self.runs[self.last_used_run_index].length
                        else:
                            sufficient_timer_for_reveals=False
                    # TODO add gpu updating somewhere here? just don't forget it
    def _send_packet_for_processing(self,characters,initial_char_offset,assigned_run):
        """sends all the necessary characters upwards in the hierarchy in order for the paragraph to handle the bulk process"""

        #Memory block identification #TODO maybe turn into a separate function
        memory_block_index = initial_char_offset // MEMORY_BLOCK_SIZE
        gpu_block_index = self.memory_blocks[memory_block_index]
        intra_block_offset = initial_char_offset % MEMORY_BLOCK_SIZE
        #Packet creation
        packet = {
            "block_id": gpu_block_index,
            "offset": intra_block_offset,
            "font_settings": assigned_run._get_all_info(),
            "local_pos": (self.x, self.y, self.z),
            "local_rot": (self.pitch, self.yaw, self.roll),
            "flags": (self.is_position_centre, self.rotate_sentence_around_paragraph,self.rotate_letters_around_sentence),
            "characters": characters
        }
        self.paragraph._receive_sentence_packet_for_processing(packet)
        # self.paragraph._receive_sentence_packet_for_processing(packet)
        #
        # packet=(self.x,self.y,self.z,self.pitch,self.yaw,self.roll,self.is_position_centre,self.rotate_around_sentence,characters)





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


# def add_new_paragraph(self, text, x=0, y=100, z=0.0, font_size=64, max_paragraph_length=500,
#                       font_bold_italic_tuple=("Arial", False, False), mode=INSTANT_TEXT, interval=0.05,
#                       pitch=0.0, yaw=0.0, roll=0.0,
#                       red=1.0, green=1.0, blue=1.0, alpha=1.0,
#                       use_centre_pivot=1):
#     """Adds a new paragraph to the text layer."""
#     if isinstance(use_centre_pivot,bool):
#         if use_centre_pivot:
#             use_centre_pivot=1
#         else:
#             use_centre_pivot=0
#     else:
#         if use_centre_pivot != 1 and use_centre_pivot!=0:
#             raise ValueError(f"use_centre_pivot when creating paragraph with text {text} needs to be 0,1 or a boolean")
#     #paragraph preparations by setting starting values
#     p_idx = len(self.paragraphs)
#     start_buffer_index = self.next_char_index
#     update_index=self.next_char_index
#     p = {
#         'typing_x': x, 'typing_y': y, 'typing_z': z,
#         'start_char_index': start_buffer_index,
#         'char_count': 0, 'total_char_reserved': 0,
#         'current_text': text,
#         'max_paragraph_length': max_paragraph_length,
#         'pending_char_queue': [], 'timer': 0.0, 'interval': interval, 'mode': mode,
#         'pitch': pitch, 'yaw': yaw, 'roll': roll,
#         'r': red, 'g': green, 'b': blue, 'a': alpha,
#         'font_size': font_size, 'font_key': font_bold_italic_tuple,
#         'centre_x': x, 'centre_y': y,
#         'use_centre_pivot': use_centre_pivot
#     }
#     self.paragraphs.append(p)
#     typing_x, typing_y = x, y
#     reveal_id, word_id = 0.0, 0.0
#     prepared_chars = []
#     min_x, max_x = float('inf'), float('-inf')
#     min_y, max_y = float('inf'), float('-inf')
#
#     #line processing in 2d
#     lines = text.split('\n')
#     for line in lines:
#         words = line.split(' ')
#         #word processing
#         for i, word in enumerate(words):
#             if not word and i != 0: continue
#
#             word_width = self.calculate_word_width(word, font_size, font_bold_italic_tuple)
#
#             #starts writing on the next line (font size*1.2) if the word position+width exceeds the paragraph length
#             if typing_x + word_width > x + max_paragraph_length:
#                 typing_x, typing_y = x, typing_y - (font_size * 1.2)
#
#             #character processing
#             for char in word:
#                 char_idx = self.next_char_index
#                 char_width = self.calculate_word_width(char, font_size, font_bold_italic_tuple)
#
#                 #calculates paragraph bounds
#                 min_x, max_x = min(min_x, typing_x), max(max_x, typing_x + char_width)
#                 min_y, max_y = min(min_y, typing_y - (font_size * 1.2)), max(max_y, typing_y)
#
#                 prepared_chars.append((char, font_bold_italic_tuple, font_size, typing_x, typing_y, z,
#                                        reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha, char_idx))
#                 typing_x += char_width
#                 self.next_char_index += 1
#                 p['total_char_reserved'] += 1
#                 reveal_id += 1.0
#
#             #space character processing
#             if i < len(words) - 1:
#                 space_width = self.calculate_word_width(' ', font_size, font_bold_italic_tuple)
#                 prepared_chars.append((' ', font_bold_italic_tuple, font_size, typing_x, typing_y, z,
#                                        reveal_id, word_id, pitch, yaw, roll, red, green, blue, alpha,
#                                        self.next_char_index))
#                 typing_x += space_width
#                 self.next_char_index += 1
#                 p['total_char_reserved'] += 1
#                 reveal_id += 1.0
#                 word_id += 1.0
#         word_id += 1.0
#         #sets the writing to begin from the next line once all words are done on the previous line
#         typing_x, typing_y = x, typing_y - (font_size * 1.2)
#
#     # centre coordinate calculation
#     if max_x > min_x:
#         p['centre_x'], p['centre_y'] = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
#
#     #if the mode is instant, a request for all the prepared characters to be processed is made immediately.
#     #Othersise, they are added to the pending character queue
#     if mode == INSTANT_TEXT:
#         for args in prepared_chars:
#             self._process_char_to_gpu(p_idx, *args, upload_now=False)
#         self.update_gpu(update_index,self.next_char_index)
#     else:
#         p['pending_char_queue'] = prepared_chars
#
#     return p_idx
# def get_font_data(self,font_key):
#     return TextHandler.fonts.get(font_key)
# def _process_char_to_gpu(self, p_idx, char, font_key, font_size, world_x, world_y, world_z=0.0,
#                          reveal_id=0.0, word_id=0.0, pitch=0.0, yaw=0.0, roll=0.0,
#                          r=1.0, g=1.0, b=1.0, a=1.0,
#                          specific_index=0, *, upload_now=False):
#     """retrieves and formats the necessary data to send to the packing function"""
#     p = self.paragraphs[p_idx]
#
#     font_data = self.get_font_data(font_key)
#     if not font_data: return 0
#     glyph_data = font_data['glyphs'].get(ord(char))
#     if not glyph_data: return 0
#
#     pcx = p.get('centre_x', world_x)
#     pcy = p.get('centre_y', world_y)
#     pcz = p.get('typing_z_start', world_z)
#     use_centre = p.get('use_centre_pivot')
#
#     handle = font_data.get('texture_handle', 0)
#     atlas_width, atlas_height = font_data['atlas_size']
#     advance = glyph_data.get('advance', 0) * font_size
#
#     h_low = (handle & 0xFFFFFFFF)
#     h_high = ((handle >> 32) & 0xFFFFFFFF)
#
#
#     #if no planebounds, send
#     if 'planeBounds' not in glyph_data:
#         self.pack_into(specific_index, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
#                        int(h_low), int(h_high),
#                        reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
#                        pcx, pcy, pcz,int(use_centre))
#     else:
#         planebounds, atlasbounds = glyph_data['planeBounds'], glyph_data['atlasBounds']
#         gxpos, gypos = world_x + (planebounds['left'] * font_size), world_y + (planebounds['bottom'] * font_size)
#         gw, gh = (planebounds['right'] - planebounds['left']) * font_size, (planebounds['top'] - planebounds['bottom']) * font_size
#         u0, v0 = atlasbounds['left'] / atlas_width, atlasbounds['bottom'] / atlas_height
#         u1, v1 = (atlasbounds['right'] - atlasbounds['left']) / atlas_width, (atlasbounds['top'] - atlasbounds['bottom']) / atlas_height
#         self.pack_into(specific_index, gxpos, gypos, gw, gh, u0, v0, u1, v1,
#                        int(h_low), int(h_high),
#                        reveal_id, word_id, world_z, pitch, yaw, roll, r, g, b, a,
#                        pcx, pcy, pcz,int(use_centre))
#
#     p['char_count'] += 1
#
#     if upload_now:
#         self.update_gpu(specific_index, specific_index + 1)
#     return advance
#
# def _update_layer(self, dt): #TODO this is the one I need
#     """dictates how many new words/letters are shown """
#     #anything revealed means the structure of the sentence has changed in any way
#     changed_sentence = False
#
#     for idx, p in enumerate(self.paragraphs):
#         #skip if all haracters have been processed
#         if not p['pending_char_queue']:
#             continue
#
#         p['timer'] += dt
#         # if time passed since the sentence was requested to show is bigger or equal
#         # to the interval of time required to display the next part of the sentence
#         if p['timer'] >= p['interval']:
#
#             #calculate how many reveals you need to show on next gpu update
#             reveals = int(p['timer'] // p['interval'])
#             #and remove "interval" amount from "timer" until timer is less than interval
#             p['timer'] %= p['interval']
#
#             #for as many reveals as are due
#             for reveal in range(reveals):
#                 #failsafe in case this runs despite the fact that there are no characters left to process
#                 if not p['pending_char_queue']:
#                     break
#
#                 first_item = p['pending_char_queue'][0]
#
#                 # if the reveal is actually a deletion
#                 if isinstance(first_item, tuple) and first_item[0] == ERASE_ACTION:
#                     cmd = p['pending_char_queue'].pop(0)
#                     self._zero_ssbo_slot(cmd[1])
#                     changed_sentence = True
#
#                 # if the reveal is meant to display words
#                 else:
#                     if p['mode'] == PER_WORD:
#                         current_reveal_id = first_item[7]  #6 is reveal ID, 7 is word ID
#                         #while there's pending characters
#                         while p['pending_char_queue']:
#                             next_item = p['pending_char_queue'][0]
#
#                             if isinstance(next_item, tuple) and next_item[0] != ERASE_ACTION and next_item[7] == current_reveal_id:
#                                 cmd = p['pending_char_queue'].pop(0)
#                                 self._process_char_to_gpu(idx, *cmd, upload_now=False)
#                                 changed_sentence = True
#                             else:
#                                 break
#                     else:
#                         cmd = p['pending_char_queue'].pop(0)
#                         self._process_char_to_gpu(idx, *cmd, upload_now=False)
#                         changed_sentence = True
#
#     if changed_sentence:
#         self.update_gpu(0,self.next_char_index)
#
#
# def update_gpu(self,start_index,end_index):
#
#     """updates a smaller part of the big text buffer"""
#     #binding the shader storage buffer as the big text buffer from the text handler
#     glBindBuffer(GL_SHADER_STORAGE_BUFFER, TextHandler.text_shader_storage_buffer)
#     start_offset = (self.buffer_offset + start_index) * _STRUCT_SIZE
#     data_size = (end_index - start_index) * _STRUCT_SIZE
#     slice_start = start_index * _STRUCT_SIZE
#     slice_end = end_index * _STRUCT_SIZE
#     raw_data = bytes(self.cpu_buffer[slice_start:slice_end])
#     glBufferSubData(GL_SHADER_STORAGE_BUFFER, start_offset, data_size, raw_data)
#
#
#     glBindBuffer(GL_SHADER_STORAGE_BUFFER,0)
#
# # def _offset_paragraph_data(self, p_idx, dx, dy):
# #     """Moves both the characters already on GPU and those waiting in the typewriter queue."""
# #     p = self.paragraphs[p_idx]
# #
# #     for i in range(p['char_count']):
# #         off = (p['start_char_index'] + i) * _STRUCT_SIZE
# #         rect = list(struct.unpack_from('<4f', self.cpu_buffer, off))
# #         struct.pack_into('<2f', self.cpu_buffer, off, rect[0] + dx, rect[1] + dy)
# #
# #
# #     if p['pending_char_queue']:
# #         new_queue = []
# #         for item in p['pending_char_queue']:
# #             l = list(item)
# #             l[3] += dx
# #             l[4] += dy
# #             new_queue.append(tuple(l))
# #         p['pending_char_queue'] = new_queue
# #
# #     self.update_gpu()
#
#
# def calculate_word_width(self, word, font_size, font_key):
#     """adds the advance (multiplied by the font size) of all viable characters in a word"""
#     return sum(self.get_glyph_data(c, font_key).get('advance', 0) * font_size for c in word if
#                self.get_glyph_data(c, font_key))
#
#
#
# def get_glyph_data(self, char, font_key):
#     """returns glyph data by turning char into its unicode value and using it as a key in the font glyph dictionary"""
#     return TextHandler.fonts.get(font_key, {}).get('glyphs', {}).get(ord(char))
#
# ############################################################################## below this line code needs to be read
# def clear_paragraph_text(self,paragraph_index):
#     """clears text from relevant paragraph"""
#     paragraph = self.paragraphs[paragraph_index]
#     # zeroes all the reserved characters of the paragraph
#     for i in range(paragraph['total_char_reserved']):
#         self._zero_ssbo_slot(paragraph['start_char_index'] + i)
#     #sets all relevant data
#     paragraph['current_text'] = ""
#     paragraph['total_char_reserved'] = 0
#     paragraph['char_count'] = 0
#     paragraph['pending_char_queue'] = []
#     return paragraph["start_char_index"],
# def set_paragraph_text(self, p_idx, text, x=USE_OWN, y=USE_OWN, z=USE_OWN, font_size=USE_OWN,
#                        font_bold_italic_tuple=USE_OWN, mode=INSTANT_TEXT, interval=None):
#     """clears the paragraph (without defragmenting it) and then calls add_text_to_paragraph on the now empty paragraph"""
#     if p_idx >= len(self.paragraphs): return False
#     p = self.paragraphs[p_idx]
#     #sets values
#     target_x = x if x is not USE_OWN else p['typing_x_start']
#     target_y = y if y is not USE_OWN else p['typing_y_start']
#     target_z = z if z is not USE_OWN else p['typing_z_start']
#     f_size = font_size if font_size is not USE_OWN else p.get('last_font_size', 64)
#     f_key = font_bold_italic_tuple if font_bold_italic_tuple is not USE_OWN else p.get('last_font_key',("Arial", False, False))
#
#     self.clear_paragraph_text(p_idx)
#     return self.add_text_to_paragraph(
#         p_idx,
#         text,
#         x=target_x,
#         y=target_y,
#         z=target_z,
#         font_size=f_size,
#         font_bold_italic_tuple=f_key,
#         mode=mode,
#         interval=interval
#     )
#
# def delete_paragraph(self, p_idx):
#     """
#     Zeros out the paragraph's buffer space and deactivates it.
#     This does not 'defragment' the buffer, it just clears the slots.
#     """
#     if p_idx >= len(self.paragraphs):
#         print(f"Warning: Attempted to delete non-existent paragraph index {p_idx}")
#         return False
#
#
#     self.update_gpu(*self.clear_paragraph_text(p_idx))
#     return True
#
#
# def optimize_layer(self):   #TODO find a way to call this every so often automatically
#     """
#     Slides all active paragraphs to the beginning of the buffer to reclaim
#     space from deleted paragraphs.
#     """
#     new_next_char_index = 0
#     sorted_paragraphs = sorted(
#         [p for p in self.paragraphs if p['total_char_reserved'] > 0],
#         key=lambda x: x['start_char_index']
#     )
#     for p in sorted_paragraphs:
#         old_start = p['start_char_index']
#         new_start = new_next_char_index
#         if old_start != new_start:
#             data_size = p['total_char_reserved'] * _STRUCT_SIZE
#             old_byte_off = old_start * _STRUCT_SIZE
#             new_byte_off = new_start * _STRUCT_SIZE
#             self.cpu_buffer[new_byte_off: new_byte_off + data_size] = \
#                 self.cpu_buffer[old_byte_off: old_byte_off + data_size]
#             p['start_char_index'] = new_start
#             if p['pending_char_queue']:
#                 new_queue = []
#                 for item in p['pending_char_queue']:
#                     l = list(item)
#                     offset_within_p = l[8] - old_start
#                     l[8] = new_start + offset_within_p
#                     new_queue.append(tuple(l))
#                 p['pending_char_queue'] = new_queue
#         new_next_char_index += p['total_char_reserved']
#     remaining_slots = self.available_characters - new_next_char_index
#     if remaining_slots > 0:
#         off = new_next_char_index * _STRUCT_SIZE
#         self.cpu_buffer[off:] = b'\x00' * (remaining_slots * _STRUCT_SIZE)
#     self.next_char_index = new_next_char_index
#     self.update_gpu()
# def add_text_to_paragraph(self, p_idx, text, x=USE_OWN, y=USE_OWN, z=USE_OWN,
#                           font_size=USE_OWN, font_bold_italic_tuple=USE_OWN,
#                           mode=USE_OWN, interval=USE_OWN,
#                           pitch=0.0, yaw=0.0, roll=0.0,
#                           red=1.0, green=1.0, blue=1.0, alpha=1.0):  #TODO remove and redo with runs
#     if p_idx >= len(self.paragraphs):
#         return False
#     p = self.paragraphs[p_idx]
#     f_size = font_size if font_size != USE_OWN else p.get('last_font_size', 64)
#     f_key = font_bold_italic_tuple if font_bold_italic_tuple != USE_OWN else p.get('last_font_key',("Arial", False, False))
#     p_mode = mode if mode != USE_OWN else p['mode']
#     p_interval = interval if interval != USE_OWN else p['interval']
#     if x != USE_OWN: p['typing_x_start'] = x
#     if y != USE_OWN: p['typing_y_start'] = y
#     if z != USE_OWN: p['typing_z_start'] = z
#     p['pitch'], p['yaw'], p['roll'] = pitch, yaw, roll
#     p['r'], p['g'], p['b'], p['a'] = red, green, blue, alpha
#     current_shadow_list = list(p.get('current_text', ""))
#     if x != USE_OWN or y != USE_OWN:
#         typing_x = p['typing_x_start']
#         typing_y = p['typing_y_start']
#     else:
#         typing_x = p.get('last_typing_x', p['typing_x_start'])
#         typing_y = p.get('last_typing_y', p['typing_y_start'])
#     current_z = p['typing_z_start']
#     reveal_id = float(p['total_char_reserved'])
#     word_id = p.get('last_word_id', 0.0)
#     max_len = p['max_paragraph_length']
#     new_prepared = []
#     lines = text.split('\n')
#     for l_idx, line in enumerate(lines):
#         words = line.split(' ')
#         for i, word in enumerate(words):
#             if not word and i != 0:
#                 continue
#             w_width = self.calculate_word_width(word, f_size, f_key)
#             if typing_x + w_width > p['typing_x_start'] + max_len:
#                 typing_x = p['typing_x_start']
#                 typing_y -= (f_size * 1.2)
#             for char in word:
#                 char_idx = p['start_char_index'] + p['total_char_reserved']
#
#                 new_prepared.append((char, f_key, f_size, typing_x, typing_y, current_z,
#                                      reveal_id, word_id, pitch, yaw, roll,
#                                      red, green, blue, alpha, char_idx))
#
#                 current_shadow_list.append(char)
#                 typing_x += self.calculate_word_width(char, f_size, f_key)
#                 p['total_char_reserved'] += 1
#                 self.next_char_index = max(self.next_char_index, char_idx + 1)
#
#                 if p_mode == PER_LETTER:
#                     reveal_id += 1.0
#             if i < len(words) - 1:
#                 char_idx = p['start_char_index'] + p['total_char_reserved']
#                 new_prepared.append((' ', f_key, f_size, typing_x, typing_y, current_z,
#                                      reveal_id, word_id, pitch, yaw, roll,
#                                      red, green, blue, alpha, char_idx))
#
#                 current_shadow_list.append(' ')
#                 typing_x += self.calculate_word_width(' ', f_size, f_key)
#                 p['total_char_reserved'] += 1
#                 self.next_char_index = max(self.next_char_index, char_idx + 1)
#
#                 if p_mode == PER_LETTER:
#                     reveal_id += 1.0
#
#             if p_mode == PER_WORD:
#                 reveal_id += 1.0
#
#             word_id += 1.0
#         if l_idx < len(lines) - 1:
#             current_shadow_list.append('\n')
#             word_id += 1.0
#             typing_x = p['typing_x_start']
#             typing_y -= (f_size * 1.2)
#     p['current_text'] = "".join(current_shadow_list)
#     p['last_typing_x'] = typing_x
#     p['last_typing_y'] = typing_y
#     p['last_word_id'] = word_id
#     p['last_font_size'] = f_size
#     p['last_font_key'] = f_key
#     p['mode'] = p_mode
#     p['interval'] = p_interval
#     p['centre_x'] = (p['typing_x_start'] + typing_x) / 2.0
#     p['centre_y'] = (p['typing_y_start'] + typing_y) / 2.0
#     if p_mode == INSTANT_TEXT:
#         for args in new_prepared:
#             self._process_char_to_gpu(p_idx, *args, upload_now=False)
#         self.update_gpu(0,self.next_char_index)
#     else:
#         p['pending_char_queue'].extend(new_prepared)
#
#     return True
#
# def delete_text_from_paragraph(self, p_idx, target, which_instance=FIRST_INSTANCE_WORD, mode=INSTANT_TEXT,
#                                interval=0.05):  #TODO revamp
#     """
#     Deletes the 'target' word from the paragraph.
#     """
#     if p_idx >= len(self.paragraphs):
#         return False
#
#     p = self.paragraphs[p_idx]
#     text = p.get('current_text', "")
#     if not text or not target:
#         return False
#
#     import re
#     target_str = str(target)
#     pattern = rf"\b{re.escape(target_str)}\b"
#     matches = list(re.finditer(pattern, text))
#
#     if not matches:
#         return False
#
#
#     if which_instance == FIRST_INSTANCE_WORD:
#         target_matches = [matches[0]]
#     elif which_instance == LAST_INSTANCE_WORD:
#         target_matches = [matches[-1]]
#     else:
#         target_matches = matches
#
#     text_list = list(text)
#     erasure_slots = []
#
#     for match in target_matches:
#         s_start, s_end = match.start(), match.end()
#         for i in range(s_start, s_end):
#             ssbo_idx = p['start_char_index'] + i
#             erasure_slots.append(ssbo_idx)
#             text_list[i] = " "
#             if p['pending_char_queue']:
#                 p['pending_char_queue'] = [
#                     q for q in p['pending_char_queue']
#                     if not (isinstance(q, tuple) and len(q) == 9 and q[8] == ssbo_idx)
#                 ]
#     if mode == INSTANT_TEXT:
#         for slot in erasure_slots:
#             self._zero_ssbo_slot(slot)
#         self.update_gpu(p["start_char_index"],p["total_char_reserved"])
#     else:
#         for slot in erasure_slots:
#             p['pending_char_queue'].append((ERASE_ACTION, slot))
#         p['mode'] = mode
#         p['interval'] = interval
#     p['current_text'] = "".join(text_list)
#     return True
# def _zero_ssbo_slot(self, ssbo_idx):
#     """sets packs the index offered into full zeroes."""
#     self.pack_into(ssbo_idx,
#                      0.0, 0.0, 0.0, 0.0,
#                      0.0, 0.0, 0.0, 0.0,
#                      0, 0,
#                      0.0, 0.0, 0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0)
# def set_paragraph_rotation(self, p_idx, pitch=USE_OWN, yaw=USE_OWN, roll=USE_OWN, use_centre_pivot=USE_OWN):
#     if p_idx >= len(self.paragraphs): return
#     p = self.paragraphs[p_idx]
#     if pitch is not USE_OWN: p['pitch'] = pitch
#     if yaw is not USE_OWN: p['yaw'] = yaw
#     if roll is not USE_OWN: p['roll'] = roll
#     if use_centre_pivot is not USE_OWN: p['use_centre_pivot'] = use_centre_pivot
#     pivot_val = 1 if p['use_centre_pivot'] else 0
#     for i in range(p['char_count']):
#         char_idx = p['start_char_index'] + i
#         off = char_idx * _STRUCT_SIZE
#         struct.pack_into('<I', self.cpu_buffer, off + 8, pivot_val)
#         struct.pack_into('<3f', self.cpu_buffer, off + 56, p['pitch'], p['yaw'], p['roll'])
#         struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], p['typing_z_start'])
#     self.update_gpu(p["start_char_index"],p["total_char_reserved"])
#
# def set_paragraph_color(self, p_idx, r=USE_OWN, g=USE_OWN, b=USE_OWN, a=USE_OWN):
#     if p_idx >= len(self.paragraphs): return
#     p = self.paragraphs[p_idx]
#     for i in range(p['char_count']):
#         char_idx = p['start_char_index'] + i
#         off = char_idx * _STRUCT_SIZE
#         color_off = off + (17 * 4)
#         current_rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)
#         new_r = r if r is not USE_OWN else current_rgba[0]
#         new_g = g if g is not USE_OWN else current_rgba[1]
#         new_b = b if b is not USE_OWN else current_rgba[2]
#         new_a = a if a is not USE_OWN else current_rgba[3]
#
#         struct.pack_into('<4f', self.cpu_buffer, color_off, new_r, new_g, new_b, new_a)
#
#     self.update_gpu(p["start_char_index"],p["total_char_reserved"])
#
# def get_paragraph_color(self, p_idx):
#     """
#     Returns the RGBA color of the first character in the paragraph.
#     """
#     if p_idx >= len(self.paragraphs):
#         return None
#
#     p = self.paragraphs[p_idx]
#     if p['char_count'] == 0:
#         return (p['r'], p['g'], p['b'], p['a'])  # Return metadata defaults if no chars exist
#
#     char_idx = p['start_char_index']
#     off = char_idx * _STRUCT_SIZE
#     color_off = off + (17 * 4)
#     rgba = struct.unpack_from('<4f', self.cpu_buffer, color_off)
#
#     return rgba
# def set_paragraph_position(self, p_idx, x=USE_OWN, y=USE_OWN, z=USE_OWN):
#     """
#     Updates the paragraph's world position by calculating the delta
#     from its current starting coordinates.
#     """
#     if p_idx >= len(self.paragraphs):
#         return False
#
#     p = self.paragraphs[p_idx]
#     target_x = x if x is not USE_OWN else p['typing_x_start']
#     target_y = y if y is not USE_OWN else p['typing_y_start']
#     target_z = z if z is not USE_OWN else p['typing_z_start']
#     dx = target_x - p['typing_x_start']
#     dy = target_y - p['typing_y_start']
#     dz = target_z - p['typing_z_start']
#     p['typing_x_start'] = target_x
#     p['typing_y_start'] = target_y
#     p['typing_z_start'] = target_z
#     p['centre_x'] += dx
#     p['centre_y'] += dy
#     if 'last_typing_x' in p:
#         p['last_typing_x'] += dx
#         p['last_typing_y'] += dy
#     for i in range(p['char_count']):
#         char_idx = p['start_char_index'] + i
#         off = char_idx * _STRUCT_SIZE
#         rect = list(struct.unpack_from('<2f', self.cpu_buffer, off + 12))
#         current_z = struct.unpack_from('<f', self.cpu_buffer, off + 52)[0]
#         struct.pack_into('<2f', self.cpu_buffer, off + 12, rect[0] + dx, rect[1] + dy)
#         struct.pack_into('<f', self.cpu_buffer, off + 52, current_z + dz)
#         struct.pack_into('<3f', self.cpu_buffer, off + 84, p['centre_x'], p['centre_y'], target_z)
#     if p['pending_char_queue']:
#         new_queue = []
#         for item in p['pending_char_queue']:
#             l = list(item)
#             l[3] += dx  # x
#             l[4] += dy  # y
#             l[5] += dz  # z
#             new_queue.append(tuple(l))
#         p['pending_char_queue'] = new_queue
#     self.update_gpu()
#     return True
#
# def change_paragraph_position(self, p_idx, x=0, y=0, z=0, relative_to=USE_OWN, change_vectorially=False):
#     if p_idx >= len(self.paragraphs):
#         return False
#
#     p = self.paragraphs[p_idx]
#     if relative_to == USE_OWN:
#         origin_x = p['typing_x_start']
#         origin_y = p['typing_y_start']
#         origin_z = p['typing_z_start']
#         rot_vec = (p['pitch'], p['yaw'], p['roll'])
#     else:
#         pos = relative_to.get_position()
#         origin_x, origin_y, origin_z = pos[0], pos[1], pos[2]
#         rot_vec = relative_to.get_rotation()
#     if change_vectorially:
#         rot_mat = glm.mat4(1.0)
#         rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[0]), glm.vec3(1, 0, 0))
#         rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[1]), glm.vec3(0, 1, 0))
#         rot_mat = glm.rotate(rot_mat, glm.radians(rot_vec[2]), glm.vec3(0, 0, 1))
#
#         direction = glm.vec3(rot_mat * glm.vec4(x, y, z, 0.0))
#         dx, dy, dz = direction.x, direction.y, direction.z
#     else:
#         dx, dy, dz = x, y, z
#     new_x = origin_x + dx
#     new_y = origin_y + dy
#     new_z = origin_z + dz
#     return self.set_paragraph_position(p_idx, x=new_x, y=new_y, z=new_z)