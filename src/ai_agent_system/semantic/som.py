"""Set-of-Mark (SoM) screenshot annotation — N2.

Draws numbered badge overlays on a screenshot PNG for every DomMark
that has a populated .bbox field.  When no bboxes are available (the
common case with Firecrawl HTML-only captures), the original bytes are
returned unchanged — the LLM can still classify via the DOM marks JSON.

Bboxes become available if N1 is later upgraded to run a lightweight
JS injection step (getBoundingClientRect per candidate element).

PIL is an optional dependency; if not installed the function degrades
gracefully (no overlay, original bytes returned).
"""

from __future__ import annotations

import io

from ai_agent_system.semantic.models import DomMark

try:
    from PIL import Image, ImageDraw, ImageFont

    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PIL_AVAILABLE = False

_BADGE_FILL = (255, 80, 0, 210)    # orange-red, semi-transparent
_BADGE_TEXT_COLOR = (255, 255, 255)
_BORDER_COLOR = (255, 80, 0, 140)
_BADGE_RADIUS = 4
_BADGE_PADDING = 2
_FONT_SIZE = 12


def render_som(screenshot_bytes: bytes, marks: list[DomMark]) -> bytes:
    """Overlay numbered badges on ``screenshot_bytes`` for marks with bbox.

    Returns PNG bytes — identical to input when PIL is unavailable or no
    mark carries a bbox.
    """
    if not _PIL_AVAILABLE:
        return screenshot_bytes

    marks_with_bbox = [m for m in marks if m.bbox is not None]
    if not marks_with_bbox:
        return screenshot_bytes

    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", _FONT_SIZE)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for mark in marks_with_bbox:
        bb = mark.bbox
        label = str(mark.mark_id)

        # Element border
        draw.rectangle(
            [bb.x, bb.y, bb.x + bb.width, bb.y + bb.height],
            outline=_BORDER_COLOR,
            width=2,
        )

        # Badge at top-left corner
        tx = bb.x + _BADGE_PADDING
        ty = bb.y + _BADGE_PADDING
        text_bbox = draw.textbbox((tx, ty), label, font=font)
        pad = _BADGE_PADDING
        rect = (
            text_bbox[0] - pad,
            text_bbox[1] - pad,
            text_bbox[2] + pad,
            text_bbox[3] + pad,
        )
        draw.rounded_rectangle(rect, radius=_BADGE_RADIUS, fill=_BADGE_FILL)
        draw.text((tx, ty), label, font=font, fill=_BADGE_TEXT_COLOR)

    composited = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    composited.save(buf, format="PNG")
    return buf.getvalue()
