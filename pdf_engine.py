"""
PDF Engine module for PDF Sign & Edit Studio.
Handles PyMuPDF operations, page rendering, annotation tracking, and high-fidelity PDF export.
"""

import io
import os
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import pymupdf
from PIL import Image, ImageOps, ImageDraw, ImageFont


@dataclass
class PDFElement:
    """Represents an interactive visual element on a PDF page."""
    id: str
    element_type: str  # 'signature', 'text', 'date', 'stamp', 'redaction', 'highlight', 'drawing'
    page_index: int
    x: float  # PDF coordinate x (points, 72 dpi)
    y: float  # PDF coordinate y (points, 72 dpi)
    width: float
    height: float
    # Optional attributes
    image_data: Optional[bytes] = None  # PNG bytes for signature / stamp / drawing
    text: str = ""
    font_size: float = 14.0
    font_name: str = "helv"  # or 'times', 'courier'
    color: str = "#000000"  # hex color
    bg_color: str = "#000000"  # for redaction / highlight
    opacity: float = 1.0  # 1.0 = opaque, 0.35 = highlight
    points: List[Tuple[float, float]] = field(default_factory=list)  # for freehand drawing
    line_width: float = 2.0


class PDFEngine:
    def __init__(self):
        self.doc: Optional[pymupdf.Document] = None
        self.file_path: Optional[str] = None
        self.elements: Dict[int, List[PDFElement]] = {}  # page_index -> list of elements
        self._element_counter = 0

    def open_pdf(self, path: str) -> bool:
        """Opens a PDF file and initializes element storage."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File non trovato: {path}")
        self.doc = pymupdf.open(path)
        self.file_path = path
        self.elements = {i: [] for i in range(len(self.doc))}
        return True

    def create_blank_pdf(self, width: float = 595.0, height: float = 842.0):
        """Creates a new blank PDF (A4 size)."""
        self.doc = pymupdf.open()
        self.doc.new_page(width=width, height=height)
        self.file_path = None
        self.elements = {0: []}

    @property
    def is_open(self) -> bool:
        return self.doc is not None and len(self.doc) > 0

    @property
    def page_count(self) -> int:
        return len(self.doc) if self.doc else 0

    def get_page_size(self, page_index: int) -> Tuple[float, float]:
        """Returns (width, height) of the page in PDF points."""
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return (595.0, 842.0)
        page = self.doc[page_index]
        rect = page.rect
        return (rect.width, rect.height)

    def render_page(self, page_index: int, zoom: float = 1.0) -> Image.Image:
        """
        Renders a PDF page to a PIL Image at the specified zoom factor.
        Base resolution is 72 dpi * 1.5 = 108 dpi for crisp rendering, multiplied by zoom.
        """
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            # Return blank dummy page
            return Image.new("RGB", (int(595 * zoom), int(842 * zoom)), (255, 255, 255))
        
        page = self.doc[page_index]
        # matrix scaling
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img

    def add_element(self, element: PDFElement):
        """Adds an interactive element to a page."""
        page_idx = element.page_index
        if page_idx not in self.elements:
            self.elements[page_idx] = []
        self.elements[page_idx].append(element)

    def remove_element(self, element_id: str):
        """Removes an element by ID."""
        for page_idx, elem_list in self.elements.items():
            for i, elem in enumerate(elem_list):
                if elem.id == element_id:
                    elem_list.pop(i)
                    return True
        return False

    def get_elements_for_page(self, page_index: int) -> List[PDFElement]:
        return self.elements.get(page_index, [])

    def clear_page_elements(self, page_index: int):
        if page_index in self.elements:
            self.elements[page_index].clear()

    def generate_id(self, prefix: str = "elem") -> str:
        self._element_counter += 1
        return f"{prefix}_{self._element_counter}"

    # Page manipulations
    def rotate_page(self, page_index: int, degrees: int = 90):
        """Rotates a page clockwise by 90/180/270 degrees."""
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return
        page = self.doc[page_index]
        page.set_rotation((page.rotation + degrees) % 360)

    def delete_page(self, page_index: int):
        """Deletes a page and shifts subsequent elements."""
        if not self.is_open or self.page_count <= 1:
            raise ValueError("Impossibile eliminare l'unica pagina del documento.")
        self.doc.delete_page(page_index)
        # Re-index elements
        new_elements = {}
        for idx, elems in self.elements.items():
            if idx < page_index:
                new_elements[idx] = elems
            elif idx > page_index:
                for el in elems:
                    el.page_index = idx - 1
                new_elements[idx - 1] = elems
        self.elements = new_elements

    def add_blank_page(self, after_index: int = -1, width: float = 595.0, height: float = 842.0):
        """Adds a blank page."""
        if not self.is_open:
            self.create_blank_pdf(width, height)
            return
        target_idx = after_index if after_index >= 0 else self.page_count - 1
        self.doc.new_page(target_idx + 1, width=width, height=height)
        # Shift elements
        new_elements = {}
        for idx, elems in self.elements.items():
            if idx <= target_idx:
                new_elements[idx] = elems
            else:
                for el in elems:
                    el.page_index = idx + 1
                new_elements[idx + 1] = elems
        new_elements[target_idx + 1] = []
        self.elements = new_elements

    # Helpers
    @staticmethod
    def hex_to_rgb_float(hex_str: str) -> Tuple[float, float, float]:
        """Converts '#RRGGBB' to (r, g, b) with values 0.0 - 1.0 for PyMuPDF."""
        hex_str = hex_str.lstrip("#")
        if len(hex_str) != 6:
            return (0.0, 0.0, 0.0)
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        return (r, g, b)

    # Save to disk
    def save_pdf(self, output_path: str):
        """
        Bakes all annotations, signatures, texts, stamps and drawings directly
        into the PDF document with vector and high-resolution embedding.
        """
        if not self.is_open:
            raise ValueError("Nessun documento PDF aperto.")

        for page_idx in range(self.page_count):
            page = self.doc[page_idx]
            page_elements = self.elements.get(page_idx, [])

            for el in page_elements:
                rect = pymupdf.Rect(el.x, el.y, el.x + el.width, el.y + el.height)

                if el.element_type in ("signature", "stamp"):
                    if el.image_data:
                        page.insert_image(rect, stream=el.image_data)

                elif el.element_type in ("text", "date"):
                    # Insert text inside rect or at point
                    rgb = self.hex_to_rgb_float(el.color)
                    fontname = el.font_name if el.font_name in ("helv", "times", "couri") else "helv"
                    # We can use insert_textbox for auto-wrap or insert_text
                    page.insert_textbox(
                        rect,
                        el.text,
                        fontsize=el.font_size,
                        fontname=fontname,
                        color=rgb,
                        align=pymupdf.TEXT_ALIGN_LEFT
                    )

                elif el.element_type == "redaction":
                    # Solid rectangle covering the area
                    fill_rgb = self.hex_to_rgb_float(el.bg_color)
                    page.draw_rect(
                        rect,
                        color=fill_rgb,
                        fill=fill_rgb,
                        width=0,
                        fill_opacity=1.0
                    )

                elif el.element_type == "highlight":
                    # Semi-transparent rectangle
                    fill_rgb = self.hex_to_rgb_float(el.bg_color)
                    page.draw_rect(
                        rect,
                        color=fill_rgb,
                        fill=fill_rgb,
                        width=0,
                        fill_opacity=el.opacity
                    )

                elif el.element_type == "drawing":
                    # Freehand drawing: either points or image
                    if el.image_data:
                        page.insert_image(rect, stream=el.image_data)
                    elif len(el.points) > 1:
                        rgb = self.hex_to_rgb_float(el.color)
                        for i in range(len(el.points) - 1):
                            p1 = pymupdf.Point(el.points[i][0], el.points[i][1])
                            p2 = pymupdf.Point(el.points[i+1][0], el.points[i+1][1])
                            page.draw_line(p1, p2, color=rgb, width=el.line_width)

        # Save document
        self.doc.save(output_path, garbage=3, deflate=True)
        # Re-open or update current path
        self.file_path = output_path
