"""
Signature Dialog module for PDF Sign & Edit Studio.
Provides 3 modes to create a signature:
1. Draw signature with mouse or pen (smoothing, colors, undo, clear)
2. Type signature with beautiful handwriting/script fonts
3. Upload signature image with automatic white background removal
"""

import io
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np


class SignatureDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_signature_created_callback):
        super().__init__(parent)
        self.title("Aggiungi Firma")
        self.geometry("750x600")
        self.minsize(700, 550)
        self.callback = on_signature_created_callback
        
        # Center the dialog
        self.lift()
        self.focus_force()
        self.grab_set()

        # State for drawing
        self.strokes = []  # list of strokes, each stroke is list of (x, y)
        self.current_stroke = []
        self.pen_color = "#0b3c5d"  # Default Dark Blue
        self.pen_width = 3
        
        # State for image upload
        self.uploaded_image = None
        self.processed_upload = None

        self._build_ui()

    def _build_ui(self):
        # Tabs using CTkTabview
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(15, 10))

        self.tab_draw = self.tabview.add("✍️ Disegna Firma")
        self.tab_type = self.tabview.add("⌨️ Digita Firma")
        self.tab_upload = self.tabview.add("📁 Carica Immagine")

        self._build_draw_tab()
        self._build_type_tab()
        self._build_upload_tab()

        # Bottom action bar
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(0, 15))

        btn_cancel = ctk.CTkButton(
            bottom_frame,
            text="Annulla",
            fg_color="#444444",
            hover_color="#555555",
            width=120,
            command=self.destroy
        )
        btn_cancel.pack(side="left")

        self.btn_apply = ctk.CTkButton(
            bottom_frame,
            text="✅ Inserisci Firma nel PDF",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=38,
            command=self._apply_current_tab_signature
        )
        self.btn_apply.pack(side="right")

    # ================= DRAW TAB =================
    def _build_draw_tab(self):
        controls = ctk.CTkFrame(self.tab_draw, fg_color="transparent")
        controls.pack(fill="x", pady=(5, 10))

        # Color picker
        lbl_col = ctk.CTkLabel(controls, text="Colore Penna:")
        lbl_col.pack(side="left", padx=(0, 8))

        colors = [
            ("Blu Penna", "#0b3c5d"),
            ("Nero", "#111111"),
            ("Blu Notte", "#001f3f"),
            ("Rosso", "#b22222")
        ]
        self.color_var = tk.StringVar(value="#0b3c5d")

        for name, hex_c in colors:
            btn = ctk.CTkRadioButton(
                controls,
                text=name,
                value=hex_c,
                variable=self.color_var,
                command=self._on_color_changed,
                fg_color=hex_c
            )
            btn.pack(side="left", padx=5)

        # Stroke width
        lbl_w = ctk.CTkLabel(controls, text="Spessore:")
        lbl_w.pack(side="left", padx=(15, 5))

        self.width_slider = ctk.CTkSlider(
            controls,
            from_=1,
            to=8,
            number_of_steps=7,
            width=100,
            command=self._on_width_changed
        )
        self.width_slider.set(self.pen_width)
        self.width_slider.pack(side="left", padx=5)

        # Action buttons: Undo & Clear
        btn_undo = ctk.CTkButton(
            controls,
            text="↩️ Annulla Tratto",
            width=110,
            fg_color="#555555",
            hover_color="#666666",
            command=self._undo_stroke
        )
        btn_undo.pack(side="right", padx=(5, 0))

        btn_clear = ctk.CTkButton(
            controls,
            text="🗑️ Cancella",
            width=90,
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=self._clear_draw_canvas
        )
        btn_clear.pack(side="right", padx=5)

        # Canvas frame
        canvas_card = ctk.CTkFrame(self.tab_draw, corner_radius=8, fg_color="#ffffff")
        canvas_card.pack(fill="both", expand=True, pady=5)

        # Inner Tkinter canvas
        self.draw_canvas = tk.Canvas(
            canvas_card,
            bg="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            cursor="crosshair"
        )
        self.draw_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Baseline indicator for signature
        self.draw_canvas.bind("<Configure>", self._draw_canvas_guidelines)
        self.draw_canvas.bind("<Button-1>", self._on_draw_start)
        self.draw_canvas.bind("<B1-Motion>", self._on_draw_move)
        self.draw_canvas.bind("<ButtonRelease-1>", self._on_draw_end)

    def _draw_canvas_guidelines(self, event=None):
        w = self.draw_canvas.winfo_width()
        h = self.draw_canvas.winfo_height()
        self.draw_canvas.delete("guideline")
        # Draw dotted baseline
        baseline_y = int(h * 0.75)
        self.draw_canvas.create_line(
            30, baseline_y, w - 30, baseline_y,
            dash=(4, 4), fill="#e2e8f0", width=1, tags="guideline"
        )
        self.draw_canvas.create_text(
            35, baseline_y + 12,
            text="✕ Linea di firma",
            anchor="w",
            fill="#94a3b8",
            font=("Arial", 9),
            tags="guideline"
        )
        self._redraw_all_strokes()

    def _on_color_changed(self):
        self.pen_color = self.color_var.get()

    def _on_width_changed(self, val):
        self.pen_width = int(val)

    def _on_draw_start(self, event):
        self.current_stroke = [(event.x, event.y)]

    def _on_draw_move(self, event):
        if not self.current_stroke:
            return
        last_x, last_y = self.current_stroke[-1]
        x, y = event.x, event.y
        self.draw_canvas.create_line(
            last_x, last_y, x, y,
            fill=self.pen_color,
            width=self.pen_width,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            tags="stroke"
        )
        self.current_stroke.append((x, y))

    def _on_draw_end(self, event):
        if self.current_stroke and len(self.current_stroke) > 1:
            self.strokes.append({
                "points": list(self.current_stroke),
                "color": self.pen_color,
                "width": self.pen_width
            })
        self.current_stroke = []

    def _redraw_all_strokes(self):
        self.draw_canvas.delete("stroke")
        for stroke in self.strokes:
            pts = stroke["points"]
            c = stroke["color"]
            w = stroke["width"]
            for i in range(len(pts) - 1):
                self.draw_canvas.create_line(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    fill=c, width=w, capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="stroke"
                )

    def _undo_stroke(self):
        if self.strokes:
            self.strokes.pop()
            self._redraw_all_strokes()

    def _clear_draw_canvas(self):
        self.strokes.clear()
        self.current_stroke.clear()
        self._redraw_all_strokes()

    def _get_drawn_signature_image(self) -> Image.Image:
        if not self.strokes:
            return None
        # Compute bounding box
        all_x = [pt[0] for s in self.strokes for pt in s["points"]]
        all_y = [pt[1] for s in self.strokes for pt in s["points"]]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        # Add margin
        margin = 15
        cw = max(1, self.draw_canvas.winfo_width())
        ch = max(1, self.draw_canvas.winfo_height())
        
        # Render high-res image
        img = Image.new("RGBA", (cw, ch), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        for s in self.strokes:
            pts = s["points"]
            col = s["color"]
            w = s["width"]
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i+1]], fill=col, width=w)

        # Crop to contents with margin
        box = (
            max(0, min_x - margin),
            max(0, min_y - margin),
            min(cw, max_x + margin),
            min(ch, max_y + margin)
        )
        cropped = img.crop(box)
        return cropped

    # ================= TYPE TAB =================
    def _build_type_tab(self):
        top_bar = ctk.CTkFrame(self.tab_type, fg_color="transparent")
        top_bar.pack(fill="x", pady=10)

        lbl = ctk.CTkLabel(top_bar, text="Inserisci Nome / Testo Firma:")
        lbl.pack(side="left", padx=(0, 10))

        self.type_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="Es. Mario Rossi",
            width=280
        )
        self.type_entry.pack(side="left", padx=5)
        self.type_entry.bind("<KeyRelease>", self._update_typed_preview)

        # Font styles
        style_frame = ctk.CTkFrame(self.tab_type, fg_color="transparent")
        style_frame.pack(fill="x", pady=5)

        lbl_s = ctk.CTkLabel(style_frame, text="Stile Calligrafico:")
        lbl_s.pack(side="left", padx=(0, 10))

        self.font_styles = {
            "Corsivo Classico (Brush Script)": "BRUSHSCI.TTF",
            "Calligrafia Elegante (Edwardian)": "ITCEDSCR.TTF",
            "Manoscritto Moderno (Ink Free)": "Inkfree.ttf",
            "Naturale (Segoe Script)": "segoesc.ttf",
            "Dinamico (Freestyle)": "FREESCPT.TTF"
        }

        self.selected_style_name = tk.StringVar(value="Corsivo Classico (Brush Script)")
        self.font_menu = ctk.CTkOptionMenu(
            style_frame,
            values=list(self.font_styles.keys()),
            variable=self.selected_style_name,
            command=self._update_typed_preview,
            width=260
        )
        self.font_menu.pack(side="left", padx=5)

        # Color
        lbl_c = ctk.CTkLabel(style_frame, text="Colore:")
        lbl_c.pack(side="left", padx=(15, 5))

        self.type_color_var = tk.StringVar(value="#0b3c5d")
        type_colors = [("Blu Penna", "#0b3c5d"), ("Nero", "#111111"), ("Blu Notte", "#001f3f")]
        for name, hex_c in type_colors:
            btn = ctk.CTkRadioButton(
                style_frame,
                text=name,
                value=hex_c,
                variable=self.type_color_var,
                command=self._update_typed_preview
            )
            btn.pack(side="left", padx=4)

        # Preview canvas
        preview_card = ctk.CTkFrame(self.tab_type, corner_radius=8, fg_color="#ffffff")
        preview_card.pack(fill="both", expand=True, pady=10)

        self.type_preview_canvas = tk.Canvas(
            preview_card,
            bg="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        self.type_preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.type_preview_image_tk = None

        self.type_entry.insert(0, "Mario Rossi")
        self.after(200, self._update_typed_preview)

    def _get_font_object(self, font_filename: str, size: int):
        font_path = os.path.join("C:/Windows/Fonts", font_filename)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _generate_typed_signature_image(self) -> Image.Image:
        text = self.type_entry.get().strip()
        if not text:
            return None
        
        style_key = self.selected_style_name.get()
        font_file = self.font_styles.get(style_key, "BRUSHSCI.TTF")
        color = self.type_color_var.get()

        font_size = 54
        font = self._get_font_object(font_file, font_size)

        # Measure text
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        d = ImageDraw.Draw(dummy_img)
        bbox = d.textbbox((0, 0), text, font=font)
        w = max(50, bbox[2] - bbox[0] + 40)
        h = max(30, bbox[3] - bbox[1] + 30)

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        # Draw text centered with offset
        draw.text((20 - bbox[0], 15 - bbox[1]), text, font=font, fill=color)
        return img

    def _update_typed_preview(self, event=None):
        img = self._generate_typed_signature_image()
        self.type_preview_canvas.delete("all")
        if img:
            cw = self.type_preview_canvas.winfo_width()
            ch = self.type_preview_canvas.winfo_height()
            if cw < 10: cw = 600
            if ch < 10: ch = 250
            
            # Draw baseline
            self.type_preview_canvas.create_line(
                30, int(ch * 0.7), cw - 30, int(ch * 0.7),
                dash=(4, 4), fill="#e2e8f0", width=1
            )

            self.type_preview_image_tk = ImageTk.PhotoImage(img)
            self.type_preview_canvas.create_image(
                cw // 2, ch // 2,
                image=self.type_preview_image_tk,
                anchor="center"
            )

    # ================= UPLOAD TAB =================
    def _build_upload_tab(self):
        top_bar = ctk.CTkFrame(self.tab_upload, fg_color="transparent")
        top_bar.pack(fill="x", pady=10)

        btn_browse = ctk.CTkButton(
            top_bar,
            text="📂 Seleziona Immagine...",
            fg_color="#0f766e",
            hover_color="#115e59",
            command=self._browse_signature_image
        )
        btn_browse.pack(side="left", padx=(0, 15))

        self.remove_bg_var = tk.BooleanVar(value=True)
        chk_bg = ctk.CTkCheckBox(
            top_bar,
            text="Rimuovi sfondo bianco (trasparenza automatica)",
            variable=self.remove_bg_var,
            command=self._process_uploaded_image
        )
        chk_bg.pack(side="left", padx=5)

        lbl_sens = ctk.CTkLabel(top_bar, text="Tolleranza:")
        lbl_sens.pack(side="left", padx=(15, 5))

        self.tol_slider = ctk.CTkSlider(
            top_bar,
            from_=150,
            to=250,
            number_of_steps=20,
            width=100,
            command=lambda v: self._process_uploaded_image()
        )
        self.tol_slider.set(215)
        self.tol_slider.pack(side="left", padx=5)

        # Preview
        preview_card = ctk.CTkFrame(self.tab_upload, corner_radius=8, fg_color="#f8fafc")
        preview_card.pack(fill="both", expand=True, pady=10)

        self.upload_preview_canvas = tk.Canvas(
            preview_card,
            bg="#f8fafc",
            bd=0,
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        self.upload_preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.upload_preview_image_tk = None

        self.upload_info_lbl = ctk.CTkLabel(
            self.tab_upload,
            text="Nessun file selezionato. Supporta PNG, JPG, JPEG, BMP.",
            text_color="#64748b"
        )
        self.upload_info_lbl.pack(pady=5)

    def _browse_signature_image(self):
        path = filedialog.askopenfilename(
            title="Seleziona Immagine Firma",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if path:
            try:
                self.uploaded_image = Image.open(path)
                self.upload_info_lbl.configure(
                    text=f"Caricato: {os.path.basename(path)} ({self.uploaded_image.width}x{self.uploaded_image.height} px)"
                )
                self._process_uploaded_image()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aprire l'immagine: {e}")

    def _process_uploaded_image(self):
        if self.uploaded_image is None:
            return
        
        img = self.uploaded_image.copy()
        
        if self.remove_bg_var.get():
            img = img.convert("RGBA")
            arr = np.array(img)
            tol = int(self.tol_slider.get())
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            mask = (r >= tol) & (g >= tol) & (b >= tol)
            arr[mask, 3] = 0
            img = Image.fromarray(arr)
            
            # Crop transparent margins
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)

        self.processed_upload = img

        # Display preview
        cw = max(50, self.upload_preview_canvas.winfo_width())
        ch = max(50, self.upload_preview_canvas.winfo_height())
        if cw < 100: cw = 600
        if ch < 100: ch = 250

        # Scale for preview keeping aspect ratio
        thumb = img.copy()
        thumb.thumbnail((cw - 40, ch - 40), Image.Resampling.LANCZOS)

        self.upload_preview_image_tk = ImageTk.PhotoImage(thumb)
        self.upload_preview_canvas.delete("all")
        self.upload_preview_canvas.create_image(
            cw // 2, ch // 2,
            image=self.upload_preview_image_tk,
            anchor="center"
        )

    # ================= APPLY =================
    def _apply_current_tab_signature(self):
        selected_tab = self.tabview.get()
        final_img = None

        if "Disegna" in selected_tab:
            final_img = self._get_drawn_signature_image()
            if not final_img:
                messagebox.showwarning("Firma Vuota", "Disegna prima la tua firma sul riquadro.")
                return

        elif "Digita" in selected_tab:
            final_img = self._generate_typed_signature_image()
            if not final_img:
                messagebox.showwarning("Campo Vuoto", "Digita il nome o le iniziali per creare la firma.")
                return

        elif "Carica" in selected_tab:
            if not self.processed_upload:
                messagebox.showwarning("Nessuna Immagine", "Seleziona prima un'immagine con la tua firma.")
                return
            final_img = self.processed_upload

        if final_img:
            # Convert to PNG bytes
            buf = io.BytesIO()
            final_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            
            # Pass image and aspect ratio to parent callback
            self.callback(final_img, img_bytes)
            self.destroy()
