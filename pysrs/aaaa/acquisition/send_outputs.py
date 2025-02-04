@staticmethod
def generate_ttl_waveform(mask_image, pixel_samples, total_x, total_y, high_voltage=5.0):
    """
    Convert a mask (PIL Image in grayscale) into a TTL waveform.
    
    - Pixels with a value > 128 are considered "active" (logic 1).
    - Each pixel is repeated 'pixel_samples' times.
    - The binary values are scaled by 'high_voltage' (e.g., 5 V for active, 0 V for inactive).
    """
    mask_arr = np.array(mask_image)
    binary_mask = (mask_arr > 128).astype(np.uint8)
    
    # If the mask dimensions do not match the scan dimensions, resize it.
    if binary_mask.shape != (total_y, total_x):
        mask_pil = Image.fromarray(binary_mask * 255)
        mask_resized = mask_pil.resize((total_x, total_y), Image.NEAREST)
        binary_mask = (np.array(mask_resized) > 128).astype(np.uint8)
    
    # For each row, repeat each pixel value 'pixel_samples' times.
    ttl_rows = [np.repeat(binary_mask[row, :], pixel_samples) for row in range(total_y)]
    ttl_wave = np.concatenate(ttl_rows)
    ttl_wave = ttl_wave * high_voltage
    return ttl_wave