import glfw
from Modular_Overly_Disorienting_Engine.Layer_0_Modules.MODEn_Settings_Module_Rendering_Branch import purpose_text
purpose_text("Handles time standardization/unification and the creation of timed functions")
from operator import itemgetter
import inspect


class TimeHandler:
    delta_time = 0
    _last_frame = 0
    _requests = {}
    _paused_requests = {}

    @staticmethod
    def _get_request_info(function_reference):
        # Safety check: itemgetter will crash if the slot was deleted mid-frame
        req = TimeHandler._requests.get(function_reference)
        if not req: return None
        return [function_reference,*itemgetter("start","duration", "clear","constant")(req)]

    @staticmethod
    def _update_dt():
        current_frame = glfw.get_time()
        TimeHandler.delta_time = current_frame - TimeHandler._last_frame
        TimeHandler._last_frame = current_frame
        for request in list(TimeHandler._requests):
            if request in TimeHandler._requests:
                TimeHandler._update_request(request)
        return TimeHandler.delta_time
    @staticmethod
    def _invoke_completion_callback(function_reference, delta_time, completion):
        """Calls a timed-function callback, tolerating callbacks that take no arguments.

        Most callbacks are written as `function_reference(delta_time=..., completion=...)`,
        but some (e.g. Sentence.signal_delay_completion in the text module) are registered
        as plain zero-argument callables. This inspects the callable's signature and only
        passes the keyword arguments it actually accepts; if inspection itself is not
        possible (e.g. some builtins/C callables), it falls back to trying the call with
        both keywords first and retrying with no arguments on a TypeError.
        """
        try:
            signature = inspect.signature(function_reference)
        except (TypeError, ValueError):
            try:
                return function_reference(delta_time=delta_time, completion=completion)
            except TypeError:
                return function_reference()

        accepts_kwargs_freely = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        kwargs = {}
        if accepts_kwargs_freely or "delta_time" in signature.parameters:
            kwargs["delta_time"] = delta_time
        if accepts_kwargs_freely or "completion" in signature.parameters:
            kwargs["completion"] = completion
        return function_reference(**kwargs)

    @staticmethod
    # Calculate progress
    def _update_request(function_reference):
        function_reference,start,duration, clear,constant_calling=TimeHandler._get_request_info(function_reference)
        now = glfw.get_time()
        t = min((now - start) / duration, 1.0)
        if t >= 1.0:
            TimeHandler._invoke_completion_callback(function_reference, TimeHandler.delta_time, t)
            if clear:
                if function_reference in TimeHandler._requests:
                    del TimeHandler._requests[function_reference]
        else:
            if constant_calling:
                TimeHandler._invoke_completion_callback(function_reference, TimeHandler.delta_time, t)
    @staticmethod
    def pause_function(function_reference):
        if function_reference in TimeHandler._requests:
            TimeHandler._paused_requests[function_reference]=TimeHandler._requests.pop(function_reference)
            TimeHandler._paused_requests[function_reference]["pause"]=TimeHandler.get_current_time()
    @staticmethod
    def unpause_function(function_reference):
        if function_reference in TimeHandler._paused_requests:
            now=TimeHandler.get_current_time()
            TimeHandler._paused_requests[function_reference]["start"]+=now-TimeHandler._paused_requests[function_reference]["pause"]
            del(TimeHandler._paused_requests[function_reference]["pause"])
            TimeHandler._requests[function_reference]=TimeHandler._paused_requests.pop(function_reference)
    @staticmethod
    def toggle_pause(function_reference):
        if function_reference in TimeHandler._requests:
            TimeHandler.pause_function(function_reference)
        else:
            TimeHandler.unpause_function(function_reference)

    @staticmethod
    def set_timed_function(function_reference, duration=None, clear_when_done=True,
                           constant_function_calling=False):
        now = glfw.get_time()

        # If it's a new request
        if function_reference not in TimeHandler._requests:
            if duration is None: return 1.0

            TimeHandler._requests[function_reference] = {
                "start": now,
                "duration": float(duration),
                "clear": clear_when_done,
                "constant":constant_function_calling
            }
    @staticmethod
    def get_elapsed_time(function_reference):
        return TimeHandler.get_current_time()-TimeHandler._requests[function_reference]["start"]
    @staticmethod
    def get_duration_time(function_reference):
        return TimeHandler._requests[function_reference]["duration"]
    @staticmethod
    def set_duration(function_reference,new_time):
        TimeHandler._requests[function_reference]["duration"]=new_time
        return new_time
    @staticmethod
    def get_current_time():
        return glfw.get_time()
    @staticmethod
    def set_clear(function_reference,clear:bool):
        TimeHandler._requests[function_reference]["clear"] = clear
        return clear
    @staticmethod
    def change_duration(function_reference, duration):
        if function_reference in TimeHandler._requests:
            TimeHandler._requests[function_reference]["duration"] += float(duration)
        else:
            print(f"Warning: Request {function_reference} not found. Cannot extend duration.")

    @staticmethod
    def set_start_time(function_reference, new_time):
        if function_reference in TimeHandler._requests:
            TimeHandler._requests[function_reference]["start"] = float(new_time)
        else:
            print(f"Warning: Request slot {function_reference} not found. Cannot extend duration.")
