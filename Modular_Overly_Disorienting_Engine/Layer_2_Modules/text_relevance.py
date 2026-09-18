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