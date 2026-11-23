"""
PDF Sign & Edit Studio - Programma visuale di visualizzazione, modifica e firma PDF.
Interfaccia moderna CustomTkinter con supporto per disegno firma, firma calligrafica,
caricamento immagine con trasparenza, caselle di testo, timbri, evidenziatore, censura e rotazione.
"""

import os
import sys
import io
import datetime
from typing import Tuple, List, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import pymupdf

from pdf_engine import PDFEngine, PDFElement
from signature_dialog import SignatureDialog

# Setup CustomTkinter appearance
ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")


class PDFEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF Sign & Edit Studio")
        self.geometry("1300x850")
        self.minsize(1050, 700)

        # Engine
        self.engine = PDFEngine()
        self.current_page = 0
        self.zoom_level = 1.25  # Base scale for crisp rendering
        
        # Interaction state
        self.active_tool = "select"  # 'select', 'pen', 'highlight', 'redact'
        self.selected_element: PDFElement = None
        self.drag_data = {"x": 0, "y": 0, "elem_x": 0, "elem_y": 0, "resizing": False, "handle": None}
        
        # Tool properties
        self.current_text_color = "#000000"
        self.current_font_size = 13.0
        self.highlight_color = "#fef08a"  # Soft yellow
        self.redact_color = "#000000"     # Blackout
        self.pen_color = "#0b3c5d"
        self.pen_width = 3.0
        self.freehand_points = []
        
        # State for text selection, area erasure and paper color sampling
        self.selected_text_words = []
        self.selected_text_rects = []
        self.selected_text_str = ""
        self.selected_area_rect = None
        self.sampled_paper_color = (1.0, 1.0, 1.0)
        self.sampled_paper_hex = "#FFFFFF"

        # Rectangle drawing state for highlight / redact / erase
        self.rect_start = None

        # Canvas items tracking
        self.page_image_tk = None
        self.element_image_refs = {}  # Keep references to PhotoImage objects
        self.canvas_page_offset = (40, 40)

        # Build UI
        self._build_menu_and_toolbar()
        self._build_main_layout()
        self._bind_shortcuts()

        # Load initial example or blank page
        sample_path = os.path.join(os.path.dirname(__file__), "esempio_contratto.pdf")
        if os.path.exists(sample_path):
            self.load_pdf(sample_path)
        else:
            self.engine.create_blank_pdf()
            self._refresh_page_view()

    # ================= UI SETUP =================
    def _build_menu_and_toolbar(self):
        # Top toolbar
        self.toolbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#1e293b")
        self.toolbar.pack(side="top", fill="x")

        # App branding / logo
        brand_lbl = ctk.CTkLabel(
            self.toolbar,
            text="📑 PDF Studio",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#38bdf8"
        )
        brand_lbl.pack(side="left", padx=(15, 20))

        # File buttons
        btn_open = ctk.CTkButton(
            self.toolbar,
            text="📂 Apri PDF",
            width=90,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.open_pdf_dialog
        )
        btn_open.pack(side="left", padx=4)

        btn_save = ctk.CTkButton(
            self.toolbar,
            text="💾 Salva",
            width=75,
            height=32,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.save_pdf
        )
        btn_save.pack(side="left", padx=4)

        btn_save_as = ctk.CTkButton(
            self.toolbar,
            text="💾 Salva con Nome",
            width=125,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.save_as_pdf
        )
        btn_save_as.pack(side="left", padx=4)

        # Undo button
        self.btn_undo = ctk.CTkButton(
            self.toolbar,
            text="↩️ Annulla",
            width=85,
            height=32,
            fg_color="#475569",
            hover_color="#64748b",
            command=self.undo_action
        )
        self.btn_undo.pack(side="left", padx=4)

        # Separator
        sep1 = ctk.CTkFrame(self.toolbar, width=2, height=28, fg_color="#475569")
        sep1.pack(side="left", padx=10)

        # Page navigation
        btn_prev = ctk.CTkButton(
            self.toolbar,
            text="◀",
            width=32,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.prev_page
        )
        btn_prev.pack(side="left", padx=(2, 4))

        self.lbl_page = ctk.CTkLabel(
            self.toolbar,
            text="Pagina 1 / 1",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f8fafc"
        )
        self.lbl_page.pack(side="left", padx=4)

        btn_next = ctk.CTkButton(
            self.toolbar,
            text="▶",
            width=32,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.next_page
        )
        btn_next.pack(side="left", padx=(4, 10))

        # Page tools
        btn_rot = ctk.CTkButton(
            self.toolbar,
            text="🔄 Ruota 90°",
            width=90,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.rotate_current_page
        )
        btn_rot.pack(side="left", padx=4)

        btn_del_page = ctk.CTkButton(
            self.toolbar,
            text="🗑️ Elimina Pagina",
            width=110,
            height=32,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self.delete_current_page
        )
        btn_del_page.pack(side="left", padx=4)

        btn_add_page = ctk.CTkButton(
            self.toolbar,
            text="➕ Nuova Pagina",
            width=110,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.add_blank_page
        )
        btn_add_page.pack(side="left", padx=4)

        # Zoom controls (Right side)
        btn_zoom_in = ctk.CTkButton(
            self.toolbar,
            text="➕",
            width=32,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.zoom_in
        )
        btn_zoom_in.pack(side="right", padx=(2, 15))

        self.lbl_zoom = ctk.CTkLabel(
            self.toolbar,
            text="125%",
            font=ctk.CTkFont(size=12),
            text_color="#cbd5e1"
        )
        self.lbl_zoom.pack(side="right", padx=4)

        btn_zoom_out = ctk.CTkButton(
            self.toolbar,
            text="➖",
            width=32,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.zoom_out
        )
        btn_zoom_out.pack(side="right", padx=(10, 2))

        btn_zoom_fit = ctk.CTkButton(
            self.toolbar,
            text="↔️ Adatta",
            width=70,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.zoom_fit_width
        )
        btn_zoom_fit.pack(side="right", padx=4)

    def _build_main_layout(self):
        # Container for Sidebar + Canvas
        self.main_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # Left Sidebar (Tools)
        self.sidebar = ctk.CTkScrollableFrame(
            self.main_container,
            width=280,
            fg_color="#1e293b",
            corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)

        self._build_sidebar_tools()

        # Center/Right Area: Canvas with scrollbars
        canvas_container = ctk.CTkFrame(self.main_container, fg_color="#090d16", corner_radius=0)
        canvas_container.pack(side="left", fill="both", expand=True)

        self.v_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical")
        self.h_scrollbar = ttk.Scrollbar(canvas_container, orient="horizontal")

        self.canvas = tk.Canvas(
            canvas_container,
            bg="#0f172a",
            bd=0,
            highlightthickness=0,
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set
        )

        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)

        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Canvas Mouse events
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)

        # Bottom status bar
        self.status_bar = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color="#0f172a")
        self.status_bar.pack(side="bottom", fill="x")

        self.status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Pronto.",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        self.status_lbl.pack(side="left", padx=15)

    def _build_sidebar_tools(self):
        # SECTION 1: FIRMA DIGITALE & GRAFICA
        sec_sign = ctk.CTkLabel(
            self.sidebar,
            text="✍️ STRUMENTI FIRMA",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        sec_sign.pack(anchor="w", padx=10, pady=(15, 6))

        btn_add_sign = ctk.CTkButton(
            self.sidebar,
            text="✍️ Crea / Inserisci Firma...",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self.open_signature_dialog
        )
        btn_add_sign.pack(fill="x", padx=10, pady=4)

        # SECTION 2: TESTO & DATI
        sec_text = ctk.CTkLabel(
            self.sidebar,
            text="🔤 TESTO & TIMBRI",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        sec_text.pack(anchor="w", padx=10, pady=(18, 6))

        btn_add_text = ctk.CTkButton(
            self.sidebar,
            text="🔤 Aggiungi Testo",
            height=34,
            fg_color="#334155",
            hover_color="#475569",
            command=self.add_text_element
        )
        btn_add_text.pack(fill="x", padx=10, pady=3)

        btn_add_date = ctk.CTkButton(
            self.sidebar,
            text="📅 Inserisci Data Odierna",
            height=34,
            fg_color="#334155",
            hover_color="#475569",
            command=self.add_date_element
        )
        btn_add_date.pack(fill="x", padx=10, pady=3)

        btn_erase_text = ctk.CTkButton(
            self.sidebar,
            text="🧹 Evidenziatore Cancella (Colore Foglio)",
            height=36,
            fg_color="#991b1b",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.activate_text_erase_mode
        )
        btn_erase_text.pack(fill="x", padx=10, pady=4)

        # Quick Stamp Dropdown
        lbl_stamp = ctk.CTkLabel(self.sidebar, text="🏷️ Timbri Predefiniti:", font=ctk.CTkFont(size=11))
        lbl_stamp.pack(anchor="w", padx=12, pady=(8, 2))

        self.stamp_options = [
            "APPROVATO",
            "FIRMATA",
            "CONFORME ALL'ORIGINALE",
            "BOZZA",
            "PAGATO",
            "RISERVATO",
            "ANNULLATO"
        ]
        self.stamp_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=self.stamp_options,
            command=self.add_stamp_element,
            fg_color="#334155",
            button_color="#475569"
        )
        self.stamp_menu.set("Seleziona timbro...")
        self.stamp_menu.pack(fill="x", padx=10, pady=3)

        # SECTION 3: ANNOTAZIONI & CENSURA
        sec_annot = ctk.CTkLabel(
            self.sidebar,
            text="🖍️ ANNOTAZIONI & STRUMENTI",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        sec_annot.pack(anchor="w", padx=10, pady=(18, 6))

        # Segmented tool mode selection
        self.tool_seg = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Cursore", "Cancella / Gomma", "Evidenzia", "Censura", "Penna"],
            command=self._on_tool_mode_changed
        )
        self.tool_seg.set("Cursore")
        self.tool_seg.pack(fill="x", padx=10, pady=4)

        # CARD FOR SELECTED TEXT / AREA TO ERASE
        self.text_erase_card = ctk.CTkFrame(self.sidebar, fg_color="#1e1b4b", corner_radius=8, border_width=1, border_color="#4338ca")
        
        lbl_te_title = ctk.CTkLabel(
            self.text_erase_card,
            text="🧹 CANCELLA PARTE DEL PDF",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#a5b4fc"
        )
        lbl_te_title.pack(anchor="w", padx=10, pady=(8, 2))

        self.lbl_selected_text_preview = ctk.CTkLabel(
            self.text_erase_card,
            text="(Nessun testo selezionato)",
            font=ctk.CTkFont(size=11),
            text_color="#e0e7ff",
            wraplength=230,
            justify="left"
        )
        self.lbl_selected_text_preview.pack(fill="x", padx=10, pady=2)

        self.lbl_paper_color_badge = ctk.CTkLabel(
            self.text_erase_card,
            text="🎨 Colore foglio rilevato: #FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_paper_color_badge.pack(anchor="w", padx=10, pady=2)

        self.btn_confirm_erase = ctk.CTkButton(
            self.text_erase_card,
            text="🗑️ Cancella con Colore Foglio",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=lambda: self.delete_selected_text(with_paper_color=True)
        )
        self.btn_confirm_erase.pack(fill="x", padx=10, pady=3)

        self.btn_erase_only_text = ctk.CTkButton(
            self.text_erase_card,
            text="✂️ Cancella Solo Testo",
            fg_color="#475569",
            hover_color="#64748b",
            font=ctk.CTkFont(size=11),
            height=28,
            command=lambda: self.delete_selected_text(with_paper_color=False)
        )
        self.btn_erase_only_text.pack(fill="x", padx=10, pady=2)

        self.btn_cancel_text_sel = ctk.CTkButton(
            self.text_erase_card,
            text="Annulla Selezione",
            fg_color="#374151",
            hover_color="#4b5563",
            height=26,
            command=self.clear_text_selection
        )
        self.btn_cancel_text_sel.pack(fill="x", padx=10, pady=(2, 8))

        # SECTION 4: PROPRIETÀ ELEMENTO SELEZIONATO
        sec_prop = ctk.CTkLabel(
            self.sidebar,
            text="⚙️ ELEMENTO SELEZIONATO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        sec_prop.pack(anchor="w", padx=10, pady=(20, 6))

        self.prop_card = ctk.CTkFrame(self.sidebar, fg_color="#0f172a", corner_radius=8)
        self.prop_card.pack(fill="x", padx=10, pady=4)

        self.lbl_selected_info = ctk.CTkLabel(
            self.prop_card,
            text="Nessun elemento selezionato.",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        self.lbl_selected_info.pack(padx=10, pady=10)

        # Dimension/Scale Slider
        self.lbl_elem_scale = ctk.CTkLabel(self.prop_card, text="Dimensione / Larghezza:")
        self.slider_elem_scale = ctk.CTkSlider(
            self.prop_card,
            from_=30,
            to=400,
            command=self._on_element_size_slider
        )

        # Text edit field (for text/date elements)
        self.lbl_elem_text = ctk.CTkLabel(self.prop_card, text="Modifica Testo:")
        self.entry_elem_text = ctk.CTkEntry(self.prop_card)
        self.entry_elem_text.bind("<KeyRelease>", self._on_element_text_edited)

        # Delete Element Button
        self.btn_del_elem = ctk.CTkButton(
            self.prop_card,
            text="🗑️ Elimina Elemento",
            fg_color="#b91c1c",
            hover_color="#991b1b",
            height=30,
            command=self.delete_selected_element
        )

        # SECTION 5: MODIFICHE SULLA PAGINA CORRENTE
        sec_list = ctk.CTkLabel(
            self.sidebar,
            text="📋 MODIFICHE PAGINA",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        sec_list.pack(anchor="w", padx=10, pady=(20, 6))

        self.page_elements_listbox = tk.Listbox(
            self.sidebar,
            bg="#0f172a",
            fg="#e2e8f0",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#334155",
            height=5
        )
        self.page_elements_listbox.pack(fill="x", padx=10, pady=4)
        self.page_elements_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        btn_clear_page = ctk.CTkButton(
            self.sidebar,
            text="Svuota Modifiche Pagina",
            fg_color="#334155",
            hover_color="#475569",
            height=28,
            command=self.clear_current_page_elements
        )
        btn_clear_page.pack(fill="x", padx=10, pady=6)

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.open_pdf_dialog())
        self.bind("<Control-s>", lambda e: self.save_pdf())
        self.bind("<Control-S>", lambda e: self.save_as_pdf())
        self.bind("<Control-z>", lambda e: self.undo_action())
        self.bind("<Control-Z>", lambda e: self.undo_action())
        self.bind("<Delete>", lambda e: self._on_delete_key())
        self.bind("<BackSpace>", lambda e: self._on_delete_key())
        self.canvas.bind("<Delete>", lambda e: self._on_delete_key())
        self.canvas.bind("<BackSpace>", lambda e: self._on_delete_key())
        self.bind("<Left>", lambda e: self.prev_page())
        self.bind("<Right>", lambda e: self.next_page())
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())

    # ================= PDF LOADING & RENDERING =================
    def load_pdf(self, path: str):
        try:
            self.engine.open_pdf(path)
            self.current_page = 0
            doc_name = os.path.basename(path)
            self.title(f"PDF Sign & Edit Studio - {doc_name}")
            self.set_status(f"Documento aperto con successo: {doc_name} ({self.engine.page_count} pagine)")
            self._refresh_page_view()
        except Exception as e:
            messagebox.showerror("Errore Apertura", f"Impossibile aprire il file PDF:\n{e}")

    def _refresh_page_view(self):
        if not self.engine.is_open:
            return

        total_pages = self.engine.page_count
        self.lbl_page.configure(text=f"Pagina {self.current_page + 1} / {total_pages}")
        self.lbl_zoom.configure(text=f"{int(self.zoom_level * 100)}%")

        # Render page via PyMuPDF
        pil_page = self.engine.render_page(self.current_page, zoom=self.zoom_level)
        self.page_image_tk = ImageTk.PhotoImage(pil_page)

        # Clear canvas
        self.canvas.delete("all")
        self.element_image_refs.clear()

        # Center page inside canvas
        ox, oy = self.canvas_page_offset
        pw, ph = pil_page.width, pil_page.height

        # Draw page shadow / frame
        shadow_offset = 6
        self.canvas.create_rectangle(
            ox + shadow_offset, oy + shadow_offset,
            ox + pw + shadow_offset, oy + ph + shadow_offset,
            fill="#050811", outline=""
        )

        # Draw page background
        self.canvas.create_image(ox, oy, anchor="nw", image=self.page_image_tk, tags="page_bg")
        # Page border
        self.canvas.create_rectangle(ox, oy, ox + pw, oy + ph, outline="#475569", width=1)

        # Configure scrollregion
        margin = 100
        self.canvas.config(scrollregion=(0, 0, ox + pw + margin, oy + ph + margin))

        # Render all page elements
        self._render_page_elements()

        # Render text selection highlights if any
        self._draw_text_selection_highlights()

        # Update sidebar list of elements
        self._refresh_elements_listbox()
        self._update_selected_element_properties()

    def _render_page_elements(self):
        ox, oy = self.canvas_page_offset
        elements = self.engine.get_elements_for_page(self.current_page)

        for el in elements:
            # Convert PDF points to canvas screen coordinates
            sx = ox + el.x * self.zoom_level
            sy = oy + el.y * self.zoom_level
            sw = el.width * self.zoom_level
            sh = el.height * self.zoom_level

            tag = f"elem_{el.id}"

            if el.element_type in ("signature", "stamp"):
                if el.image_data:
                    # Open original image and scale to current zoom
                    raw_img = Image.open(io.BytesIO(el.image_data))
                    scaled_img = raw_img.resize((max(10, int(sw)), max(10, int(sh))), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(scaled_img)
                    self.element_image_refs[el.id] = img_tk
                    self.canvas.create_image(sx, sy, anchor="nw", image=img_tk, tags=(tag, "interactive"))

            elif el.element_type in ("text", "date"):
                # Render text on canvas
                font_sz = max(8, int(el.font_size * self.zoom_level))
                self.canvas.create_text(
                    sx, sy,
                    text=el.text,
                    font=("Helvetica", font_sz),
                    fill=el.color,
                    anchor="nw",
                    tags=(tag, "interactive")
                )

            elif el.element_type == "redaction":
                self.canvas.create_rectangle(
                    sx, sy, sx + sw, sy + sh,
                    fill=el.bg_color,
                    outline="",
                    tags=(tag, "interactive")
                )

            elif el.element_type == "highlight":
                # Stipple or semi-translucent rectangle
                self.canvas.create_rectangle(
                    sx, sy, sx + sw, sy + sh,
                    fill=el.bg_color,
                    outline="",
                    stipple="gray50",
                    tags=(tag, "interactive")
                )

            elif el.element_type == "drawing":
                if el.image_data:
                    raw_img = Image.open(io.BytesIO(el.image_data))
                    scaled_img = raw_img.resize((max(10, int(sw)), max(10, int(sh))), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(scaled_img)
                    self.element_image_refs[el.id] = img_tk
                    self.canvas.create_image(sx, sy, anchor="nw", image=img_tk, tags=(tag, "interactive"))
                elif len(el.points) > 1:
                    scaled_pts = []
                    for pt in el.points:
                        scaled_pts.extend([ox + pt[0] * self.zoom_level, oy + pt[1] * self.zoom_level])
                    self.canvas.create_line(
                        *scaled_pts,
                        fill=el.color,
                        width=max(1, int(el.line_width * self.zoom_level)),
                        capstyle=tk.ROUND,
                        joinstyle=tk.ROUND,
                        tags=(tag, "interactive")
                    )

            # Draw selection frame & handles if this element is selected
            if self.selected_element and self.selected_element.id == el.id:
                # Bounding box
                self.canvas.create_rectangle(
                    sx - 2, sy - 2, sx + sw + 2, sy + sh + 2,
                    outline="#38bdf8",
                    width=2,
                    dash=(4, 4),
                    tags="selection_box"
                )
                # Resize handle at bottom-right
                handle_sz = 8
                hx = sx + sw
                hy = sy + sh
                self.canvas.create_rectangle(
                    hx - handle_sz, hy - handle_sz, hx + handle_sz, hy + handle_sz,
                    fill="#38bdf8",
                    outline="#ffffff",
                    tags=("resize_handle", "selection_box")
                )

    # ================= MOUSE & CANVAS INTERACTIONS =================
    def _canvas_to_pdf_coords(self, cx: float, cy: float) -> Tuple[float, float]:
        ox, oy = self.canvas_page_offset
        px = (cx - ox) / self.zoom_level
        py = (cy - oy) / self.zoom_level
        return (px, py)

    def _on_canvas_press(self, event):
        self.canvas.focus_set()
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px, py = self._canvas_to_pdf_coords(cx, cy)

        # 1. Text / Area Erase Mode (Higlight & Erase with paper color)
        if self.active_tool in ("erase_text", "erase_paper_color"):
            self.rect_start = (px, py, cx, cy)
            self.canvas.delete("text_sel_highlight")
            self.canvas.delete("temp_sel_rect")
            self.canvas.delete("temp_word_highlight")
            self.selected_text_words.clear()
            self.selected_text_rects.clear()
            self.selected_text_str = ""
            self.selected_area_rect = None
            self._update_text_erase_card()
            return

        # 2. Pen tool mode
        if self.active_tool == "pen":
            self.freehand_points = [(px, py)]
            return

        # 3. Highlight or Redaction drawing mode
        if self.active_tool in ("highlight", "redact"):
            self.rect_start = (px, py, cx, cy)
            return

        # 4. Selection / Movement mode
        # Check if clicked on resize handle of selected element
        if self.selected_element:
            ox, oy = self.canvas_page_offset
            el = self.selected_element
            sw = el.width * self.zoom_level
            sh = el.height * self.zoom_level
            hx = ox + el.x * self.zoom_level + sw
            hy = oy + el.y * self.zoom_level + sh
            
            if abs(cx - hx) <= 12 and abs(cy - hy) <= 12:
                self.drag_data["resizing"] = True
                self.drag_data["x"] = cx
                self.drag_data["y"] = cy
                self.drag_data["elem_w"] = el.width
                self.drag_data["elem_h"] = el.height
                return

        # Check if clicked inside any element on current page (top to bottom order)
        clicked_elem = None
        elements = self.engine.get_elements_for_page(self.current_page)
        for el in reversed(elements):
            if el.x <= px <= el.x + el.width and el.y <= py <= el.y + el.height:
                clicked_elem = el
                break

        if clicked_elem:
            self.selected_element = clicked_elem
            self.drag_data["resizing"] = False
            self.drag_data["x"] = cx
            self.drag_data["y"] = cy
            self.drag_data["elem_x"] = clicked_elem.x
            self.drag_data["elem_y"] = clicked_elem.y
            self.set_status(f"Elemento selezionato: {clicked_elem.element_type.capitalize()}. Trascina per spostarlo.")
        else:
            self.selected_element = None

        self._refresh_page_view()

    def _on_canvas_drag(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px, py = self._canvas_to_pdf_coords(cx, cy)

        # Text / Area selection drag (Highlighter eraser with paper color sampling)
        if self.active_tool in ("erase_text", "erase_paper_color") and self.rect_start:
            start_px, start_py, start_cx, start_cy = self.rect_start
            self.canvas.delete("temp_sel_rect")
            self.canvas.delete("temp_word_highlight")
            # Draw dashed selection rectangle with warm highlighter tint
            self.canvas.create_rectangle(
                start_cx, start_cy, cx, cy,
                fill="#fed7aa", outline="#ea580c", width=2, dash=(4, 3),
                stipple="gray25", tags="temp_sel_rect"
            )
            # Find and highlight intersecting words
            sel_rect = pymupdf.Rect(min(start_px, px), min(start_py, py), max(start_px, px), max(start_py, py))
            words = self.engine.get_page_words(self.current_page)
            ox, oy = self.canvas_page_offset
            for w in words:
                w_rect = pymupdf.Rect(w[0], w[1], w[2], w[3])
                if sel_rect.intersects(w_rect):
                    wx0 = ox + w[0] * self.zoom_level
                    wy0 = oy + w[1] * self.zoom_level
                    wx1 = ox + w[2] * self.zoom_level
                    wy1 = oy + w[3] * self.zoom_level
                    self.canvas.create_rectangle(
                        wx0, wy0, wx1, wy1,
                        fill="#fb923c", stipple="gray50", outline="#c2410c", width=1,
                        tags="temp_word_highlight"
                    )
            return

        # Pen drawing
        if self.active_tool == "pen" and self.freehand_points:
            last_pt = self.freehand_points[-1]
            ox, oy = self.canvas_page_offset
            self.canvas.create_line(
                ox + last_pt[0] * self.zoom_level, oy + last_pt[1] * self.zoom_level,
                cx, cy,
                fill=self.pen_color, width=max(1, int(self.pen_width * self.zoom_level)),
                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="temp_drawing"
            )
            self.freehand_points.append((px, py))
            return

        # Highlight or Redaction rectangle preview
        if self.active_tool in ("highlight", "redact") and self.rect_start:
            _, _, start_cx, start_cy = self.rect_start
            self.canvas.delete("temp_rect")
            fill_c = self.highlight_color if self.active_tool == "highlight" else self.redact_color
            stipple_val = "gray50" if self.active_tool == "highlight" else ""
            self.canvas.create_rectangle(
                start_cx, start_cy, cx, cy,
                fill=fill_c, outline="#38bdf8", width=1,
                stipple=stipple_val, tags="temp_rect"
            )
            return

        # Resizing element
        if self.drag_data.get("resizing") and self.selected_element:
            dx = (cx - self.drag_data["x"]) / self.zoom_level
            new_w = max(20.0, self.drag_data["elem_w"] + dx)
            # Maintain aspect ratio for signatures/stamps
            if self.selected_element.element_type in ("signature", "stamp"):
                aspect = self.drag_data["elem_h"] / max(1.0, self.drag_data["elem_w"])
                new_h = new_w * aspect
            else:
                dy = (cy - self.drag_data["y"]) / self.zoom_level
                new_h = max(15.0, self.drag_data["elem_h"] + dy)

            self.selected_element.width = new_w
            self.selected_element.height = new_h
            self._refresh_page_view()
            return

        # Dragging element
        if self.selected_element and not self.drag_data.get("resizing"):
            dx = (cx - self.drag_data["x"]) / self.zoom_level
            dy = (cy - self.drag_data["y"]) / self.zoom_level
            self.selected_element.x = self.drag_data["elem_x"] + dx
            self.selected_element.y = self.drag_data["elem_y"] + dy
            self._refresh_page_view()

    def _on_canvas_release(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px, py = self._canvas_to_pdf_coords(cx, cy)

        # Text / Area erase selection release
        if self.active_tool in ("erase_text", "erase_paper_color") and self.rect_start:
            start_px, start_py, _, _ = self.rect_start
            self.canvas.delete("temp_sel_rect")
            self.canvas.delete("temp_word_highlight")
            self.rect_start = None

            x0, x1 = min(start_px, px), max(start_px, px)
            y0, y1 = min(start_py, py), max(start_py, py)
            w, h = x1 - x0, y1 - y0

            if w > 2 and h > 2:
                sel_rect = pymupdf.Rect(x0, y0, x1, y1)
                
                # Sample paper color
                sampled_rgb = self.engine.sample_paper_color(self.current_page, sel_rect)
                r, g, b = int(sampled_rgb[0] * 255), int(sampled_rgb[1] * 255), int(sampled_rgb[2] * 255)
                hex_c = f"#{r:02X}{g:02X}{b:02X}"
                self.sampled_paper_color = sampled_rgb
                self.sampled_paper_hex = hex_c

                words = self.engine.get_page_words(self.current_page)
                matched = [w for w in words if sel_rect.intersects(pymupdf.Rect(w[:4]))]

                self.selected_area_rect = sel_rect
                self.selected_text_words = matched
                self.selected_text_rects = [pymupdf.Rect(w[:4]) for w in matched]

                if matched:
                    self.selected_text_str = " ".join(w[4] for w in matched)
                    self.set_status(f"Scritto selezionato ({len(matched)} parole). Colore foglio: {hex_c}. Premi [CANC] o 'Cancella con Colore Foglio'.")
                else:
                    self.selected_text_str = f"Parte del PDF ({int(w)}x{int(h)} pt)"
                    self.set_status(f"Parte del PDF selezionata ({int(w)}x{int(h)} pt). Colore foglio: {hex_c}. Premi [CANC] per eliminare.")

                self._draw_text_selection_highlights()
                self._update_text_erase_card()
            return

        # Pen stroke finish
        if self.active_tool == "pen" and len(self.freehand_points) > 1:
            all_x = [p[0] for p in self.freehand_points]
            all_y = [p[1] for p in self.freehand_points]
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)

            new_el = PDFElement(
                id=self.engine.generate_id("draw"),
                element_type="drawing",
                page_index=self.current_page,
                x=min_x,
                y=min_y,
                width=max(5.0, max_x - min_x),
                height=max(5.0, max_y - min_y),
                points=list(self.freehand_points),
                color=self.pen_color,
                line_width=self.pen_width
            )
            self.engine.add_element(new_el)
            self.freehand_points = []
            self.canvas.delete("temp_drawing")
            self._refresh_page_view()
            return

        # Highlight or Redaction finish
        if self.active_tool in ("highlight", "redact") and self.rect_start:
            start_px, start_py, _, _ = self.rect_start
            x0, x1 = min(start_px, px), max(start_px, px)
            y0, y1 = min(start_py, py), max(start_py, py)
            w, h = x1 - x0, y1 - y0

            if w > 5 and h > 5:
                elem_type = self.active_tool
                bg_col = self.highlight_color if elem_type == "highlight" else self.redact_color
                new_el = PDFElement(
                    id=self.engine.generate_id("rect"),
                    element_type=elem_type,
                    page_index=self.current_page,
                    x=x0,
                    y=y0,
                    width=w,
                    height=h,
                    bg_color=bg_col,
                    opacity=0.35 if elem_type == "highlight" else 1.0
                )
                self.engine.add_element(new_el)
                self.selected_element = new_el

            self.rect_start = None
            self.canvas.delete("temp_rect")
            self.tool_seg.set("Cursore")
            self.active_tool = "select"
            self._refresh_page_view()
            return

        self.drag_data["resizing"] = False

    def _on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mouse_wheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_ctrl_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    # ================= TOOLS ACTIONS =================
    def _on_tool_mode_changed(self, mode):
        mapping = {
            "Cursore": "select",
            "Cancella / Gomma": "erase_paper_color",
            "Cancella Testo": "erase_paper_color",
            "Evidenzia": "highlight",
            "Evidenziatore": "highlight",
            "Censura": "redact",
            "Penna": "pen"
        }
        self.active_tool = mapping.get(mode, "select")
        if self.active_tool == "select":
            self.canvas.config(cursor="arrow")
            self.set_status("Modalità Selezione: clicca e trascina per spostare o ridimensionare gli elementi.")
        elif self.active_tool == "erase_paper_color":
            self.canvas.config(cursor="crosshair")
            self.set_status("Evidenziatore Cancella-Scritto attivo: trascina sullo scritto per cancellarlo prendendo il colore del foglio.")
        elif self.active_tool == "pen":
            self.canvas.config(cursor="pencil")
            self.set_status("Modalità Penna: disegna direttamente sulla pagina PDF.")
        else:
            self.canvas.config(cursor="crosshair")
            self.set_status(f"Modalità {mode}: trascina con il mouse per tracciare un rettangolo.")

    def activate_text_erase_mode(self):
        self.tool_seg.set("Cancella / Gomma")
        self.active_tool = "erase_paper_color"
        self.canvas.config(cursor="crosshair")
        self.selected_element = None
        self.set_status("Evidenziatore Cancella-Scritto attivo: trascina sullo scritto per cancellarlo con il colore del foglio.")
        self._refresh_page_view()

    def _draw_text_selection_highlights(self):
        self.canvas.delete("text_sel_highlight")
        ox, oy = self.canvas_page_offset
        if self.selected_area_rect:
            r = self.selected_area_rect
            sx0 = ox + r.x0 * self.zoom_level
            sy0 = oy + r.y0 * self.zoom_level
            sx1 = ox + r.x1 * self.zoom_level
            sy1 = oy + r.y1 * self.zoom_level
            self.canvas.create_rectangle(
                sx0, sy0, sx1, sy1,
                fill="#fdba74", stipple="gray25", outline="#ea580c", width=2, dash=(4, 2),
                tags="text_sel_highlight"
            )
            # Corner markers for selected area
            cs = 6
            for (cx, cy) in [(sx0, sy0), (sx1, sy0), (sx0, sy1), (sx1, sy1)]:
                self.canvas.create_rectangle(
                    cx - cs, cy - cs, cx + cs, cy + cs,
                    fill="#ea580c", outline="#ffffff", width=1,
                    tags="text_sel_highlight"
                )

        if self.selected_text_rects:
            for r in self.selected_text_rects:
                sx0 = ox + r.x0 * self.zoom_level
                sy0 = oy + r.y0 * self.zoom_level
                sx1 = ox + r.x1 * self.zoom_level
                sy1 = oy + r.y1 * self.zoom_level
                self.canvas.create_rectangle(
                    sx0, sy0, sx1, sy1,
                    fill="#fb923c", stipple="gray50", outline="#c2410c", width=1,
                    tags="text_sel_highlight"
                )

    def _update_text_erase_card(self):
        if self.selected_text_str or self.selected_area_rect:
            preview = self.selected_text_str or "Area selezionata"
            if len(preview) > 55:
                preview = preview[:52] + "..."
            self.lbl_selected_text_preview.configure(text=f'"{preview}"')
            self.lbl_paper_color_badge.configure(text=f"🎨 Colore foglio: {self.sampled_paper_hex}")
            
            # Show "Cancella solo testo" only if text was detected
            if self.selected_text_words:
                self.btn_erase_only_text.pack(fill="x", padx=10, pady=2, before=self.btn_cancel_text_sel)
            else:
                self.btn_erase_only_text.pack_forget()

            self.text_erase_card.pack(fill="x", padx=10, pady=8, after=self.prop_card)
        else:
            self.lbl_selected_text_preview.configure(text="(Nessun testo selezionato)")
            self.text_erase_card.pack_forget()

    def clear_text_selection(self):
        self.selected_text_words.clear()
        self.selected_text_rects.clear()
        self.selected_text_str = ""
        self.selected_area_rect = None
        self.canvas.delete("text_sel_highlight")
        self.canvas.delete("temp_sel_rect")
        self.canvas.delete("temp_word_highlight")
        self._update_text_erase_card()
        self.set_status("Selezione cancellata.")

    def delete_selected_text(self, with_paper_color: bool = True):
        if not self.engine.is_open:
            return

        if not self.selected_area_rect and not self.selected_text_rects:
            messagebox.showinfo("Nessuna Selezione", "Seleziona prima lo scritto o l'area da cancellare.")
            return

        deleted_info = self.selected_text_str or "Area selezionata"
        color_info = self.sampled_paper_hex

        if with_paper_color and self.selected_area_rect:
            self.engine.erase_with_paper_color(self.current_page, self.selected_area_rect, custom_color=self.sampled_paper_color)
            self.set_status(f"Scritto cancellato con successo col colore del foglio ({color_info}).")
        elif self.selected_text_rects:
            self.engine.erase_selected_words(self.current_page, self.selected_text_rects, fill_color=self.sampled_paper_color)
            self.set_status(f"Testo eliminato dal PDF col colore del foglio: '{deleted_info}'")
        elif self.selected_area_rect:
            self.engine.erase_rect_area(self.current_page, self.selected_area_rect, fill_color=self.sampled_paper_color)
            self.set_status(f"Area cancellata con successo ({color_info}).")

        self.clear_text_selection()
        self._refresh_page_view()

    def undo_action(self):
        if not self.engine.is_open:
            return
        if self.engine.undo():
            self.clear_text_selection()
            self.selected_element = None
            self.set_status("Operazione annullata con successo! Ripristinato stato precedente.")
            self._refresh_page_view()
        else:
            self.set_status("Nessuna operazione da annullare.")

    def _on_delete_key(self, event=None):
        if self.selected_area_rect or self.selected_text_rects:
            self.delete_selected_text(with_paper_color=True)
        elif self.selected_element:
            self.delete_selected_element()

    def open_signature_dialog(self):
        SignatureDialog(self, on_signature_created_callback=self._on_signature_ready)

    def _on_signature_ready(self, pil_image: Image.Image, img_bytes: bytes):
        # Calculate size in points
        aspect = pil_image.height / max(1, pil_image.width)
        w_points = 150.0
        h_points = w_points * aspect

        # Place centered in visible viewport
        page_w, page_h = self.engine.get_page_size(self.current_page)
        px = max(20.0, (page_w - w_points) / 2)
        py = max(20.0, page_h - h_points - 80.0)  # Near bottom by default

        new_el = PDFElement(
            id=self.engine.generate_id("sig"),
            element_type="signature",
            page_index=self.current_page,
            x=px,
            y=py,
            width=w_points,
            height=h_points,
            image_data=img_bytes
        )
        self.engine.add_element(new_el)
        self.selected_element = new_el
        self.set_status("Firma aggiunta! Trascinala per posizionarla esattamente dove desideri.")
        self._refresh_page_view()

    def add_text_element(self):
        # Popup entry dialog
        dialog = ctk.CTkInputDialog(
            text="Inserisci il testo da posizionare sul PDF:",
            title="Aggiungi Testo"
        )
        text = dialog.get_input()
        if text and text.strip():
            page_w, page_h = self.engine.get_page_size(self.current_page)
            new_el = PDFElement(
                id=self.engine.generate_id("txt"),
                element_type="text",
                page_index=self.current_page,
                x=50.0,
                y=100.0,
                width=max(120.0, len(text) * 8.0),
                height=25.0,
                text=text.strip(),
                font_size=self.current_font_size,
                color=self.current_text_color
            )
            self.engine.add_element(new_el)
            self.selected_element = new_el
            self.set_status("Testo aggiunto. Trascinalo nella posizione desiderata.")
            self._refresh_page_view()

    def add_date_element(self):
        today_str = datetime.date.today().strftime("%d/%m/%Y")
        new_el = PDFElement(
            id=self.engine.generate_id("date"),
            element_type="date",
            page_index=self.current_page,
            x=50.0,
            y=120.0,
            width=100.0,
            height=22.0,
            text=today_str,
            font_size=12.0,
            color="#1e293b"
        )
        self.engine.add_element(new_el)
        self.selected_element = new_el
        self.set_status(f"Data inserita ({today_str}). Trascinala dove vuoi.")
        self._refresh_page_view()

    def add_stamp_element(self, stamp_name):
        if stamp_name not in self.stamp_options:
            return
        
        # Color palettes for stamps
        colors = {
            "APPROVATO": "#16a34a",
            "FIRMATA": "#2563eb",
            "CONFORME ALL'ORIGINALE": "#0f766e",
            "BOZZA": "#ea580c",
            "PAGATO": "#059669",
            "RISERVATO": "#dc2626",
            "ANNULLATO": "#991b1b"
        }
        color_hex = colors.get(stamp_name, "#2563eb")

        # Generate stamp image
        w, h = 240, 80
        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        
        d.rounded_rectangle([(3, 3), (w-3, h-3)], radius=10, outline=color_hex, width=3)
        d.rounded_rectangle([(8, 8), (w-8, h-8)], radius=6, outline=color_hex, width=1)
        
        try:
            font_main = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 20)
            font_sub = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 10)
        except Exception:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        bbox = d.textbbox((0, 0), stamp_name, font=font_main)
        tw = bbox[2] - bbox[0]
        d.text(((w - tw) // 2, 18), stamp_name, font=font_main, fill=color_hex)

        subtext = "DATA: " + datetime.date.today().strftime("%d/%m/%Y")
        bbox_s = d.textbbox((0, 0), subtext, font=font_sub)
        sw = bbox_s[2] - bbox_s[0]
        d.text(((w - sw) // 2, 50), subtext, font=font_sub, fill=color_hex)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        new_el = PDFElement(
            id=self.engine.generate_id("stamp"),
            element_type="stamp",
            page_index=self.current_page,
            x=60.0,
            y=60.0,
            width=140.0,
            height=140.0 * (h / w),
            image_data=img_bytes
        )
        self.engine.add_element(new_el)
        self.selected_element = new_el
        self.stamp_menu.set("Seleziona timbro...")
        self.set_status(f"Timbro '{stamp_name}' inserito.")
        self._refresh_page_view()

    # ================= SELECTION & EDIT PROPERTIES =================
    def _update_selected_element_properties(self):
        if not self.selected_element:
            self.lbl_selected_info.configure(text="Nessun elemento selezionato.")
            self.slider_elem_scale.pack_forget()
            self.lbl_elem_scale.pack_forget()
            self.entry_elem_text.pack_forget()
            self.lbl_elem_text.pack_forget()
            self.btn_del_elem.pack_forget()
            return

        el = self.selected_element
        t_name = el.element_type.capitalize()
        self.lbl_selected_info.configure(text=f"Selezionato: {t_name} (ID: {el.id})")

        # Size slider
        self.lbl_elem_scale.pack(padx=10, pady=(4, 2))
        self.slider_elem_scale.pack(fill="x", padx=10, pady=(0, 6))
        self.slider_elem_scale.set(el.width)

        # Text editing
        if el.element_type in ("text", "date"):
            self.lbl_elem_text.pack(padx=10, pady=(4, 2))
            self.entry_elem_text.pack(fill="x", padx=10, pady=(0, 6))
            self.entry_elem_text.delete(0, "end")
            self.entry_elem_text.insert(0, el.text)
        else:
            self.lbl_elem_text.pack_forget()
            self.entry_elem_text.pack_forget()

        # Delete button
        self.btn_del_elem.pack(fill="x", padx=10, pady=(6, 10))

    def _on_element_size_slider(self, val):
        if not self.selected_element:
            return
        old_w = self.selected_element.width
        new_w = float(val)
        aspect = self.selected_element.height / max(1.0, old_w)
        self.selected_element.width = new_w
        if self.selected_element.element_type in ("signature", "stamp"):
            self.selected_element.height = new_w * aspect
        self._refresh_page_view()

    def _on_element_text_edited(self, event=None):
        if not self.selected_element or self.selected_element.element_type not in ("text", "date"):
            return
        new_txt = self.entry_elem_text.get()
        self.selected_element.text = new_txt
        self.selected_element.width = max(60.0, len(new_txt) * 8.5)
        self._refresh_page_view()

    def delete_selected_element(self):
        if not self.selected_element:
            return
        self.engine.remove_element(self.selected_element.id)
        self.selected_element = None
        self.set_status("Elemento eliminato.")
        self._refresh_page_view()

    def clear_current_page_elements(self):
        if messagebox.askyesno("Conferma", "Vuoi cancellare tutte le modifiche apportate su questa pagina?"):
            self.engine.clear_page_elements(self.current_page)
            self.selected_element = None
            self.set_status("Modifiche della pagina rimosse.")
            self._refresh_page_view()

    def _refresh_elements_listbox(self):
        self.page_elements_listbox.delete(0, "end")
        elements = self.engine.get_elements_for_page(self.current_page)
        for i, el in enumerate(elements):
            desc = el.element_type.capitalize()
            if el.text:
                desc += f": '{el.text[:15]}'"
            self.page_elements_listbox.insert("end", f"{i+1}. {desc}")

    def _on_listbox_select(self, event):
        sel = self.page_elements_listbox.curselection()
        if sel:
            idx = sel[0]
            elements = self.engine.get_elements_for_page(self.current_page)
            if 0 <= idx < len(elements):
                self.selected_element = elements[idx]
                self._refresh_page_view()

    # ================= PAGE NAVIGATION & TOOLS =================
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_element = None
            self._refresh_page_view()

    def next_page(self):
        if self.current_page < self.engine.page_count - 1:
            self.current_page += 1
            self.selected_element = None
            self._refresh_page_view()

    def rotate_current_page(self):
        self.engine.rotate_page(self.current_page, 90)
        self.set_status(f"Pagina {self.current_page + 1} ruotata di 90°.")
        self._refresh_page_view()

    def delete_current_page(self):
        if self.engine.page_count <= 1:
            messagebox.showwarning("Attenzione", "Impossibile eliminare l'unica pagina del documento.")
            return
        if messagebox.askyesno("Elimina Pagina", f"Sei sicuro di voler eliminare la pagina {self.current_page + 1}?"):
            self.engine.delete_page(self.current_page)
            if self.current_page >= self.engine.page_count:
                self.current_page = max(0, self.engine.page_count - 1)
            self.selected_element = None
            self.set_status("Pagina eliminata.")
            self._refresh_page_view()

    def add_blank_page(self):
        self.engine.add_blank_page(after_index=self.current_page)
        self.current_page += 1
        self.selected_element = None
        self.set_status(f"Nuova pagina vuota aggiunta alla posizione {self.current_page + 1}.")
        self._refresh_page_view()

    # ================= ZOOM =================
    def zoom_in(self):
        if self.zoom_level < 3.0:
            self.zoom_level += 0.15
            self._refresh_page_view()

    def zoom_out(self):
        if self.zoom_level > 0.4:
            self.zoom_level -= 0.15
            self._refresh_page_view()

    def zoom_fit_width(self):
        cw = self.canvas.winfo_width()
        pw, _ = self.engine.get_page_size(self.current_page)
        if cw > 100 and pw > 0:
            self.zoom_level = max(0.4, min(2.5, (cw - 120) / pw))
            self._refresh_page_view()

    # ================= FILE OPERATIONS =================
    def open_pdf_dialog(self):
        path = filedialog.askopenfilename(
            title="Seleziona Documento PDF",
            filetypes=[("Documenti PDF", "*.pdf")]
        )
        if path:
            self.load_pdf(path)

    def save_pdf(self):
        if not self.engine.is_open:
            return
        if self.engine.file_path:
            try:
                self.engine.save_pdf(self.engine.file_path)
                self.set_status(f"File salvato con successo: {os.path.basename(self.engine.file_path)}")
                messagebox.showinfo("Salvataggio", "Documento salvato con successo!")
            except Exception as e:
                # If cannot overwrite open file directly, suggest Save As
                self.save_as_pdf()
        else:
            self.save_as_pdf()

    def save_as_pdf(self):
        if not self.engine.is_open:
            return
        path = filedialog.asksaveasfilename(
            title="Salva PDF Modificato e Firmato",
            defaultextension=".pdf",
            filetypes=[("Documenti PDF", "*.pdf")]
        )
        if path:
            try:
                self.engine.save_pdf(path)
                self.set_status(f"File salvato con successo come: {os.path.basename(path)}")
                messagebox.showinfo("Salvataggio", f"Documento salvato con successo in:\n{path}")
            except Exception as e:
                messagebox.showerror("Errore Salvataggio", f"Errore durante il salvataggio:\n{e}")

    def set_status(self, msg: str):
        self.status_lbl.configure(text=msg)


if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
