import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

def create_gradient(width, height, start_color, end_color):
    base = Image.new('RGBA', (width, height), start_color)
    top = Image.new('RGBA', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        for x in range(width):
            mask_data.append(int(255 * (y / height)))
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def draw_scrum_brain_logo(draw, center_x, center_y, size, color):
    """Draws a stylized brain/circuit logo representing AI + Scrum."""
    # Dimensions
    radius = size // 2
    stroke_width = max(2, size // 15)
    
    # 1. The "Brain" / Cloud shape (3 circles)
    # Top circle
    top_r = size // 4
    draw.ellipse((center_x - top_r, center_y - size//2, center_x + top_r, center_y), outline=color, width=stroke_width)
    
    # Bottom Left circle
    bl_r = size // 3.5
    draw.ellipse((center_x - size//2, center_y - size//6, center_x - size//2 + 2*bl_r, center_y - size//6 + 2*bl_r), outline=color, width=stroke_width)
    
    # Bottom Right circle
    br_r = size // 3.5
    draw.ellipse((center_x + size//2 - 2*br_r, center_y - size//6, center_x + size//2, center_y - size//6 + 2*br_r), outline=color, width=stroke_width)
    
    # 2. "Circuit" nodes (dots) inside
    dot_r = max(2, size // 12)
    # Center node
    draw.ellipse((center_x - dot_r, center_y - dot_r, center_x + dot_r, center_y + dot_r), fill=color)
    
    # Connections
    # Draw logic lines connecting center to lobes
    draw.line((center_x, center_y, center_x, center_y - size//3), fill=color, width=stroke_width)
    draw.line((center_x, center_y, center_x - size//3, center_y + size//6), fill=color, width=stroke_width)
    draw.line((center_x, center_y, center_x + size//3, center_y + size//6), fill=color, width=stroke_width)

def generate_icons():
    os.makedirs("appPackage", exist_ok=True)
    
    # --- 1. Color Icon (192x192) ---
    # Requirement: Full-bleed, square, logo within 120x120 safe area
    size = 192
    safe_area = 120
    
    # Deep purple/blue gradient background
    bg_start = (75, 50, 150, 255)  # Teams Purple-ish
    bg_end = (30, 20, 60, 255)     # Darker bottom
    img_color = create_gradient(size, size, bg_start, bg_end)
    draw_color = ImageDraw.Draw(img_color)
    
    # Draw logo in safe area
    # Center point
    cx, cy = size // 2, size // 2
    # Logo size (keep inside 120x120)
    logo_size = 100 
    
    draw_scrum_brain_logo(draw_color, cx, cy, logo_size, (255, 255, 255, 255))
    
    color_path = os.path.join("appPackage", "color.png")
    img_color.save(color_path, "PNG")
    print(f"Created Color Icon: {color_path}")
    
    # --- 2. Outline Icon (32x32) ---
    # Requirement: Monochrome, transparent PNG (white on transparent), no padding
    size = 32
    img_outline = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw_outline = ImageDraw.Draw(img_outline)
    
    # Draw logo full size (no padding as requested "fit cleanly")
    # But keep small margin to avoid cutting off stroke
    margin = 2
    logo_size = size - (margin * 2)
    cx, cy = size // 2, size // 2
    
    draw_scrum_brain_logo(draw_outline, cx, cy, logo_size, (255, 255, 255, 255))
    
    outline_path = os.path.join("appPackage", "outline.png")
    img_outline.save(outline_path, "PNG")
    print(f"Created Outline Icon: {outline_path}")

if __name__ == "__main__":
    generate_icons()
