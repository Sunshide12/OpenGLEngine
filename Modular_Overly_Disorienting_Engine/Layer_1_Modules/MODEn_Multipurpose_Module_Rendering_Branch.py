import glfw
from Modular_Overly_Disorienting_Engine import TimeHandler


#TODO add more shit related to monitors
def get_monitor_size(which_monitor=None):
    monitor = glfw.get_primary_monitor()
    video_mode = glfw.get_video_mode(monitor)
    return video_mode.size.width,video_mode.size.height

def linear_ramping(current_value:int|float, target_value:int|float, step:int|float):
    """
    Increments value toward a target by a fixed step per second.
    """
    if current_value < target_value:
        # Increase speed, but don't overshoot target
        return min(current_value + step * TimeHandler.delta_time, target_value)
    elif current_value > target_value:
        # Decrease speed (deceleration)
        return max(current_value - step * TimeHandler.delta_time, target_value)
    return current_value
def linear_interpolation_ramping(current_value, target_value, frame_step_weight, dt):
    """
    Moves a percentage of the remaining distance every frame.
    Ideal for: Camera smoothing or 'organic' following.
    Note: lerp_factor should be between 0 and 1 (e.g., 0.1 for 10% per frame).
    """
    # We use (1 - lerp_factor**dt) to make the lerp frame-rate independent
    # This ensures it feels the same at 30fps and 144fps.
    t = 1 - pow(1 - frame_step_weight, dt)
    return current_value + (target_value - current_value) * t
def get_smooth_value_dt(start_val, target_val, elapsed_time, target_time, dt):
    """
    Calculates position based on an S-Curve over a fixed duration.
    elapsed_time: must be updated manually each frame (elapsed_time += dt)
    """
    # Increment our local progress tracker
    current_elapsed = elapsed_time + dt

    # Calculate completion percentage (0.0 to 1.0)
    t = max(0, min(current_elapsed / target_time, 1.0))

    # Apply Smoothstep formula for acceleration/deceleration
    smooth_t = t * t * (3 - 2 * t)

    new_value = start_val + (target_val - start_val) * smooth_t
    return new_value, current_elapsed
