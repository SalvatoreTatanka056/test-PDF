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


# Registry of available Windows fonts with style variants
FONT_REGISTRY = {
    "Arial": {
        "regular": "C:/Windows/Fonts/arial.ttf",
        "bold": "C:/Windows/Fonts/arialbd.ttf",
        "italic": "C:/Windows/Fonts/ariali.ttf",
        "bolditalic": "C:/Windows/Fonts/arialbi.ttf"
    },
    "Times New Roman": {
        "regular": "C:/Windows/Fonts/times.ttf",
        "bold": "C:/Windows/Fonts/timesbd.ttf",
        "italic": "C:/Windows/Fonts/timesi.ttf",
        "bolditalic": "C:/Windows/Fonts/timesbi.ttf"
    },
    "Calibri": {
        "regular": "C:/Windows/Fonts/calibri.ttf",
        "bold": "C:/Windows/Fonts/calibrib.ttf",
        "italic": "C:/Windows/Fonts/calibrii.ttf",
        "bolditalic": "C:/Windows/Fonts/calibriz.ttf"
    },
    "Segoe UI": {
        "regular": "C:/Windows/Fonts/segoeui.ttf",
        "bold": "C:/Windows/Fonts/segoeuib.ttf",
        "italic": "C:/Windows/Fonts/segoeuii.ttf",
        "bolditalic": "C:/Windows/Fonts/segoeuiz.ttf"
    },
    "Courier New": {
        "regular": "C:/Windows/Fonts/cour.ttf",
        "bold": "C:/Windows/Fonts/courbd.ttf",
        "italic": "C:/Windows/Fonts/couri.ttf",
        "bolditalic": "C:/Windows/Fonts/courbi.ttf"
    },
    "Georgia": {
        "regular": "C:/Windows/Fonts/georgia.ttf",
        "bold": "C:/Windows/Fonts/georgiab.ttf",
        "italic": "C:/Windows/Fonts/georgiai.ttf",
        "bolditalic": "C:/Windows/Fonts/georgiaz.ttf"
    },
    "Verdana": {
        "regular": "C:/Windows/Fonts/verdana.ttf",
        "bold": "C:/Windows/Fonts/verdanab.ttf",
        "italic": "C:/Windows/Fonts/verdanai.ttf",
        "bolditalic": "C:/Windows/Fonts/verdanaz.ttf"
    },
    "Comic Sans MS": {
        "regular": "C:/Windows/Fonts/comic.ttf",
        "bold": "C:/Windows/Fonts/comicbd.ttf",
        "italic": "C:/Windows/Fonts/comici.ttf",
        "bolditalic": "C:/Windows/Fonts/comicz.ttf"
    },
    "Brush Script MT": {
        "regular": "C:/Windows/Fonts/BRUSHSCI.TTF",
        "bold": "C:/Windows/Fonts/BRUSHSCI.TTF",
        "italic": "C:/Windows/Fonts/BRUSHSCI.TTF",
        "bolditalic": "C:/Windows/Fonts/BRUSHSCI.TTF"
    },
    "Ink Free": {
        "regular": "C:/Windows/Fonts/Inkfree.ttf",
        "bold": "C:/Windows/Fonts/Inkfree.ttf",
        "italic": "C:/Windows/Fonts/Inkfree.ttf",
        "bolditalic": "C:/Windows/Fonts/Inkfree.ttf"
    }
}


def get_font_path(font_family: str, bold: bool = False, italic: bool = False) -> Optional[str]:
    styles = FONT_REGISTRY.get(font_family)
    if not styles:
        return None
    key = "regular"
    if bold and italic:
        key = "bolditalic"
    elif bold:
        key = "bold"
    elif italic:
        key = "italic"
    
    path = styles.get(key) or styles.get("regular")
    if path and os.path.exists(path):
        return path
    return None


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
    font_family: str = "Arial"  # Arial, Times New Roman, Calibri, etc.
    font_bold: bool = False
    font_italic: bool = False
    font_name: str = "helv"  # fallback
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
        self.undo_stack: List[Tuple[bytes, Dict[int, List[PDFElement]]]] = []

    def push_undo(self):
        """Saves current state for undo."""
        if not self.is_open:
            return
        doc_bytes = self.doc.tobytes()
        import copy
        elements_copy = copy.deepcopy(self.elements)
        self.undo_stack.append((doc_bytes, elements_copy))
        if len(self.undo_stack) > 15:
            self.undo_stack.pop(0)

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def undo(self) -> bool:
        """Restores the previous document state."""
        if not self.can_undo():
            return False
        doc_bytes, elements_copy = self.undo_stack.pop()
        if self.doc:
            self.doc.close()
        self.doc = pymupdf.open("pdf", doc_bytes)
        self.elements = elements_copy
        return True

    def open_pdf(self, path: str) -> bool:
        """Opens a PDF file and initializes element storage."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File non trovato: {path}")
        self.doc = pymupdf.open(path)
        self.file_path = path
        self.elements = {i: [] for i in range(len(self.doc))}
        self.undo_stack.clear()
        return True

    def create_blank_pdf(self, width: float = 595.0, height: float = 842.0):
        """Creates a new blank PDF (A4 size)."""
        self.doc = pymupdf.open()
        self.doc.new_page(width=width, height=height)
        self.file_path = None
        self.elements = {0: []}
        self.undo_stack.clear()

    def close(self):
        """Closes the document and releases resources."""
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass
            self.doc = None
        self.file_path = None
        self.elements.clear()
        self.undo_stack.clear()

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

    def _map_pdf_font_to_family(self, font_name: str) -> Tuple[str, str]:
        """
        Maps a PDF internal font name (e.g. 'ABCDEF+TimesNewRomanPS-BoldMT', 'Helvetica')
        to one of the supported FONT_REGISTRY families and provides a descriptive label.
        """
        import re
        clean = re.sub(r'^[A-Z]{6}\+', '', font_name)
        fn_lower = clean.lower().replace('-', '').replace(' ', '').replace('_', '')

        if 'times' in fn_lower or 'roman' in fn_lower:
            return 'Times New Roman', f"{clean} (Times New Roman)"
        elif 'calibri' in fn_lower:
            return 'Calibri', f"{clean} (Calibri)"
        elif 'arial' in fn_lower:
            return 'Arial', f"{clean} (Arial)"
        elif 'helvetica' in fn_lower:
            return 'Arial', f"{clean} (Compatibile con Arial)"
        elif 'segoe' in fn_lower:
            return 'Segoe UI', f"{clean} (Segoe UI)"
        elif 'courier' in fn_lower:
            return 'Courier New', f"{clean} (Courier New)"
        elif 'georgia' in fn_lower:
            return 'Georgia', f"{clean} (Georgia)"
        elif 'verdana' in fn_lower:
            return 'Verdana', f"{clean} (Verdana)"
        elif 'comic' in fn_lower:
            return 'Comic Sans MS', f"{clean} (Comic Sans)"
        elif 'brush' in fn_lower:
            return 'Brush Script MT', f"{clean} (Brush Script)"
        elif 'inkfree' in fn_lower or 'ink free' in fn_lower:
            return 'Ink Free', f"{clean} (Ink Free)"
        elif 'consolas' in fn_lower:
            return 'Courier New', f"{clean} (Monospazio Courier New)"
        elif 'tahoma' in fn_lower:
            return 'Segoe UI', f"{clean} (Simile a Segoe UI)"
        elif 'cambria' in fn_lower or 'garamond' in fn_lower:
            return 'Georgia', f"{clean} (Serif Georgia)"
        elif 'trebuchet' in fn_lower:
            return 'Segoe UI', f"{clean} (Segoe UI)"
        else:
            return 'Arial', clean

    def get_document_fonts(self, page_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Analyzes and extracts all fonts used in the document (or a specific page),
        including font name, mapped standard family, detected font sizes, colors,
        and frequency/count of usage.
        """
        if not self.is_open:
            return []

        if page_index is not None and 0 <= page_index < self.page_count:
            pages_to_check = [page_index]
        else:
            pages_to_check = range(self.page_count)

        font_stats = {}

        for p_idx in pages_to_check:
            try:
                page = self.doc[p_idx]
                d = page.get_text("dict")
                for b in d.get("blocks", []):
                    for l in b.get("lines", []):
                        for s in l.get("spans", []):
                            raw_font = s.get("font", "").strip()
                            if not raw_font:
                                continue
                            txt = s.get("text", "").strip()
                            if not txt:
                                continue
                            
                            size = round(s.get("size", 12.0), 1)
                            c = s.get("color", 0)
                            hex_color = f"#{(c>>16)&0xFF:02x}{(c>>8)&0xFF:02x}{c&0xFF:02x}"
                            flags = s.get("flags", 0)
                            is_italic = bool(flags & 2) or ("italic" in raw_font.lower()) or ("oblique" in raw_font.lower())
                            is_bold = bool(flags & 16) or ("bold" in raw_font.lower()) or ("black" in raw_font.lower())

                            if raw_font not in font_stats:
                                font_stats[raw_font] = {
                                    "raw_name": raw_font,
                                    "count": 0,
                                    "sizes": set(),
                                    "colors": set(),
                                    "bold": is_bold,
                                    "italic": is_italic,
                                    "samples": []
                                }
                            font_stats[raw_font]["count"] += len(txt)
                            font_stats[raw_font]["sizes"].add(size)
                            font_stats[raw_font]["colors"].add(hex_color)
                            if is_bold:
                                font_stats[raw_font]["bold"] = True
                            if is_italic:
                                font_stats[raw_font]["italic"] = True
                            if len(font_stats[raw_font]["samples"]) < 2:
                                font_stats[raw_font]["samples"].append(txt[:40])
            except Exception:
                pass

        # Fallback to page.get_fonts() if no text spans were found
        if not font_stats:
            for p_idx in pages_to_check:
                try:
                    page = self.doc[p_idx]
                    for f_info in page.get_fonts():
                        basefont = f_info[3] if len(f_info) > 3 else ""
                        if basefont and basefont not in font_stats:
                            font_stats[basefont] = {
                                "raw_name": basefont,
                                "count": 1,
                                "sizes": {12.0},
                                "colors": {"#000000"},
                                "bold": "bold" in basefont.lower(),
                                "italic": "italic" in basefont.lower() or "oblique" in basefont.lower(),
                                "samples": []
                            }
                except Exception:
                    pass

        results = []
        for raw_name, st in font_stats.items():
            mapped_fam, friendly_desc = self._map_pdf_font_to_family(raw_name)
            sorted_sizes = sorted(list(st["sizes"]))
            dominant_size = sorted_sizes[0] if sorted_sizes else 12.0
            for sz in sorted_sizes:
                if 9.5 <= sz <= 14.5:
                    dominant_size = sz
                    break

            dominant_color = "#000000"
            for col in st["colors"]:
                if col.lower() in ("#000000", "#0f172a", "#1e293b", "#334155"):
                    dominant_color = col
                    break
            else:
                if st["colors"]:
                    dominant_color = list(st["colors"])[0]

            results.append({
                "raw_name": raw_name,
                "friendly_name": friendly_desc,
                "family": mapped_fam,
                "sizes": sorted_sizes,
                "dominant_size": dominant_size,
                "color": dominant_color,
                "bold": st["bold"],
                "italic": st["italic"],
                "count": st["count"],
                "samples": st["samples"]
            })

        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    # Page manipulations
    def get_page_words(self, page_index: int) -> List[Tuple]:
        """Returns list of word tuples: (x0, y0, x1, y1, word, block_no, line_no, word_no)"""
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return []
        page = self.doc[page_index]
        return page.get_text("words")

    def erase_selected_words(self, page_index: int, word_rects: List[pymupdf.Rect], fill_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bool:
        """
        Permanently redacts/erases specific word rectangles from the PDF content stream,
        filling the area with the background color (default white).
        """
        if not self.is_open or page_index < 0 or page_index >= self.page_count or not word_rects:
            return False
        self.push_undo()
        page = self.doc[page_index]
        for r in word_rects:
            page.add_redact_annot(r, fill=fill_color)
        page.apply_redactions()
        return True

    def sample_paper_color(self, page_index: int, rect: pymupdf.Rect) -> Tuple[float, float, float]:
        """
        Samples the surrounding background paper color near rect.
        Returns (r, g, b) float tuple in 0.0 - 1.0 range.
        """
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return (1.0, 1.0, 1.0)
        page = self.doc[page_index]
        pix = page.get_pixmap()
        w, h = pix.width, pix.height
        x0, y0, x1, y1 = max(0, int(rect.x0)), max(0, int(rect.y0)), min(w - 1, int(rect.x1)), min(h - 1, int(rect.y1))

        # Sample perimeter pixels (around the writing)
        samples = []
        points = [
            (x0, max(0, y0 - 3)), (x1, max(0, y0 - 3)),
            (min(w - 1, x1 + 3), (y0 + y1) // 2), (max(0, x0 - 3), (y0 + y1) // 2),
            (x0, min(h - 1, y1 + 3)), (x1, min(h - 1, y1 + 3)),
            (x0, y0), (x1, y1), ((x0 + x1) // 2, max(0, y0 - 2))
        ]
        for px, py in points:
            if 0 <= px < w and 0 <= py < h:
                samples.append(pix.pixel(px, py)[:3])

        if not samples:
            return (1.0, 1.0, 1.0)
        # Select the brightest sample (paper background is typically brightest)
        samples.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
        brightest = samples[-1]
        return tuple(c / 255.0 for c in brightest)

    def erase_with_paper_color(self, page_index: int, rect: pymupdf.Rect, custom_color: Optional[Tuple[float, float, float]] = None) -> Tuple[float, float, float]:
        """
        Erases writing and content inside rect, filling with the automatically
        sampled paper color (or custom_color).
        """
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return (1.0, 1.0, 1.0)
        
        fill_col = custom_color if custom_color is not None else self.sample_paper_color(page_index, rect)
        self.erase_rect_area(page_index, rect, fill_color=fill_col)
        return fill_col

    def erase_rect_area(self, page_index: int, rect: pymupdf.Rect, fill_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bool:
        """
        Permanently redacts/erases all text, graphics and content within the given rectangle,
        and removes any user-added annotations/elements inside that region.
        """
        if not self.is_open or page_index < 0 or page_index >= self.page_count:
            return False
        self.push_undo()
        page = self.doc[page_index]
        page.add_redact_annot(rect, fill=fill_color)
        page.apply_redactions()

        # Also remove any added overlay elements in that area
        if page_index in self.elements:
            remaining = []
            for el in self.elements[page_index]:
                el_rect = pymupdf.Rect(el.x, el.y, el.x + el.width, el.y + el.height)
                if not rect.intersects(el_rect):
                    remaining.append(el)
            self.elements[page_index] = remaining

        return True

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
                    # Insert text with custom font if available
                    rgb = self.hex_to_rgb_float(el.color)
                    font_path = get_font_path(el.font_family, el.font_bold, el.font_italic)
                    
                    if font_path and os.path.exists(font_path):
                        internal_name = f"f_{el.id}"
                        page.insert_font(fontname=internal_name, fontfile=font_path)
                        fontname = internal_name
                    else:
                        fontname = el.font_name if el.font_name in ("helv", "times", "couri") else "helv"

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

        # Save document cleanly using bytes buffer to prevent Windows in-place file lock issues
        pdf_bytes = self.doc.tobytes(garbage=3, deflate=True)
        self.doc.close()
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        
        # Re-open document and reset elements
        self.doc = pymupdf.open(output_path)
        self.elements = {i: [] for i in range(len(self.doc))}
        self.file_path = output_path
