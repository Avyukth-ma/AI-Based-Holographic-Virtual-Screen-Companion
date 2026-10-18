import base64
import io
import logging
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

logger = logging.getLogger("companion.avatar")
logger.setLevel(logging.INFO)

class AvatarEngine:
    """
    Generates and caches holographic AI avatar frames using Pillow.
    Uses PNG format to preserve alpha transparency for web rendering.
    """
    
    def __init__(self, size=256):
        self.size = size
        self.base_image = self._create_base_core()
        
        # Color mapping for states (R, G, B)
        self.state_colors = {
            "idle": (0, 255, 255),       # Cyan
            "sleep": (50, 100, 150),     # Dimmed slate blue
            "thinking": (180, 0, 255),   # Purple
            "speaking": (255, 180, 0),   # Golden
            "error": (255, 0, 0),        # Red
        }
        
        # Cache for static states to save CPU cycles
        self.cache = {}
        self._pregenerate_static_states()
        
    def _create_base_core(self) -> Image.Image:
        """Draws a geometric sci-fi core to act as the base holographic shape."""
        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        center = self.size // 2
        
        # Outer ring
        draw.ellipse(
            [center - 100, center - 100, center + 100, center + 100],
            outline=(255, 255, 255, 150),
            width=4
        )
        
        # Dashed inner ring
        for i in range(0, 360, 30):
            draw.arc(
                [center - 80, center - 80, center + 80, center + 80],
                start=i,
                end=i + 15,
                fill=(255, 255, 255, 200),
                width=3
            )
            
        # Inner core
        draw.ellipse(
            [center - 50, center - 50, center + 50, center + 50],
            fill=(255, 255, 255, 220)
        )
        
        return img

    def _apply_hologram_effect(self, state: str, audio_level: float = 0.0) -> Image.Image:
        """Applies tint, scanlines, and neon glow to the base image."""
        img = self.base_image.copy()
        color = self.state_colors.get(state, self.state_colors["idle"])
        
        # 1. Apply Tint (Colorize)
        # Convert white pixels to the target color while keeping alpha
        pixels = img.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                if a > 0:
                    pixels[x, y] = (color[0], color[1], color[2], a)
                    
        # 2. Add Scanlines
        draw = ImageDraw.Draw(img)
        scanline_width = 3 if state == "error" else 1
        scanline_spacing = 6 if state == "error" else 4
        
        for y in range(0, img.height, scanline_spacing):
            draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, 80 if state == "error" else 50), width=scanline_width)
            
        # 3. Apply Glow (Gaussian Blur)
        # Create a blurred copy and composite it behind/over the original
        blur_radius = 10 if state != "speaking" else 10 + int(audio_level * 20)
        if state == "sleep":
            blur_radius = 0  # No glow for sleep state
        glow = img.filter(ImageFilter.GaussianBlur(blur_radius))
        
        # Increase glow brightness for speaking state
        if state == "speaking" and audio_level > 0:
            enhancer = ImageEnhance.Brightness(glow)
            glow = enhancer.enhance(1.0 + audio_level * 1.5)
            
        # Composite original over glow
        final_img = Image.alpha_composite(glow.convert("RGBA"), img)
        
        # Dimming effect for sleep state
        if state == "sleep":
            enhancer = ImageEnhance.Brightness(final_img)
            final_img = enhancer.enhance(0.4)  # Dim brightness to 40%
            
        return final_img

    def _image_to_base64(self, img: Image.Image) -> str:
        """Encodes PIL Image to base64 PNG."""
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _pregenerate_static_states(self):
        """Caches static states on startup."""
        logger.info("Pre-generating static holographic frames...")
        for state in ["idle", "thinking", "error", "sleep"]:
            img = self._apply_hologram_effect(state)
            self.cache[state] = self._image_to_base64(img)
        logger.info("Static frames cached successfully.")

    def get_frame(self, state: str = "idle", audio_level: float = 0.0) -> str:
        """
        Returns a base64 PNG of the avatar.
        Uses cache for static states to optimize CPU usage.
        """
        if state in ["idle", "thinking", "sleep"] and state in self.cache:
            return self.cache[state]
            
        # Dynamically generate speaking frame based on audio reactivity
        img = self._apply_hologram_effect(state, audio_level)
        return self._image_to_base64(img)

_engine_instance = None

def get_avatar_engine() -> AvatarEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AvatarEngine()
    return _engine_instance
