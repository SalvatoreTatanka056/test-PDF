"""
Text Dialog module for PDF Sign & Edit Studio.
Provides a modern visual dialog to insert text with custom font family,
font size, bold/italic styles, color palette, live preview,
and automatic detection & adoption of the document's original fonts.
"""

import tkinter as tk
from tkinter import colorchooser
from typing import List, Dict, Any, Optional
import customtkinter as ctk

FONT_FAMILIES = [
    "Arial",
    "Times New Roman",
    "Calibri",
    "Segoe UI",
    "Courier New",
    "Georgia",
    "Verdana",
    "Comic Sans MS",
    "Brush Script MT",
    "Ink Free"
]

COLOR_PALETTE = [
    ("Nero", "#000000"),
    ("Blu Notte", "#0f172a"),
    ("Blu Penna", "#1d4ed8"),
    ("Rosso", "#dc2626"),
    ("Verde Foresta", "#15803d"),
    ("Grigio Antracite", "#475569")
]


class AddTextDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        initial_text="",
        font_family="Arial",
        font_size=14,
        font_bold=False,
        font_italic=False,
        color="#000000",
        detected_fonts: Optional[List[Dict[str, Any]]] = None,
        callback=None
    ):
        super().__init__(parent)
        self.title("Inserisci e Formatta Testo - PDF Sign & Edit Studio")
        self.geometry("680x640")
        self.minsize(620, 580)
        self.callback = callback
        self.detected_fonts = detected_fonts or []

        self.font_family = font_family if font_family in FONT_FAMILIES else "Arial"
        self.font_size = int(font_size)
        self.font_bold = font_bold
        self.font_italic = font_italic
        self.text_color = color

        self.lift()
        self.focus_force()
        self.grab_set()

        self._build_ui(initial_text)

    def _build_ui(self, initial_text):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 6))

        lbl_title = ctk.CTkLabel(
            header,
            text="🔤 Personalizzazione Testo & Carattere",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_title.pack(side="left")

        # -------------------------------------------------------------
        # SECTION 1: DETECTED DOCUMENT FONTS (Font Usati nel Documento)
        # -------------------------------------------------------------
        doc_card = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=8, border_width=1, border_color="#334155")
        doc_card.pack(fill="x", padx=20, pady=(4, 8))

        doc_header = ctk.CTkFrame(doc_card, fg_color="transparent")
        doc_header.pack(fill="x", padx=12, pady=(8, 2))

        lbl_doc_badge = ctk.CTkLabel(
            doc_header,
            text="📄 FONT RILEVATO NEL DOCUMENTO PDF:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#6ee7b7"
        )
        lbl_doc_badge.pack(side="left")

        self.lbl_feedback = ctk.CTkLabel(
            doc_header,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_feedback.pack(side="right")

        if self.detected_fonts:
            # We list the detected fonts and provide quick-apply buttons
            fonts_container = ctk.CTkFrame(doc_card, fg_color="transparent")
            fonts_container.pack(fill="x", padx=12, pady=(2, 8))

            for i, f_info in enumerate(self.detected_fonts[:3]):
                row = ctk.CTkFrame(fonts_container, fg_color="#1e293b", corner_radius=6)
                row.pack(fill="x", pady=2)

                raw_n = f_info.get("raw_name", "Sconosciuto")
                friendly = f_info.get("friendly_name", raw_n)
                fam = f_info.get("family", "Arial")
                sizes = f_info.get("sizes", [])
                sizes_str = ", ".join([f"{int(s) if s.is_integer() else s} pt" for s in sizes[:4]])
                dom_size = f_info.get("dominant_size", 12.0)
                col = f_info.get("color", "#000000")
                is_b = f_info.get("bold", False)
                is_i = f_info.get("italic", False)

                desc_text = f"• {friendly}   |   Misure nel file: {sizes_str}"
                lbl_desc = ctk.CTkLabel(
                    row,
                    text=desc_text,
                    font=ctk.CTkFont(size=11),
                    text_color="#f1f5f9"
                )
                lbl_desc.pack(side="left", padx=8, pady=4)

                btn_apply = ctk.CTkButton(
                    row,
                    text=f"✨ Adotta {fam} ({int(dom_size)} pt)",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="#0284c7",
                    hover_color="#0369a1",
                    height=26,
                    command=lambda f=f_info: self._apply_detected_font(f)
                )
                btn_apply.pack(side="right", padx=6, pady=4)
        else:
            lbl_none = ctk.CTkLabel(
                doc_card,
                text="Nessun testo vettoriale rilevato nel PDF (documento scansionato o pagina vuota).",
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8"
            )
            lbl_none.pack(anchor="w", padx=12, pady=(2, 8))

        # -------------------------------------------------------------
        # SECTION 2: TEXT INPUT
        # -------------------------------------------------------------
        input_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8)
        input_frame.pack(fill="x", padx=20, pady=(2, 6))

        lbl_input = ctk.CTkLabel(input_frame, text="Testo da inserire:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_input.pack(anchor="w", padx=12, pady=(6, 2))

        self.entry_text = ctk.CTkEntry(
            input_frame,
            placeholder_text="Digita qui il testo...",
            font=ctk.CTkFont(size=13),
            height=34
        )
        self.entry_text.pack(fill="x", padx=12, pady=(0, 8))
        self.entry_text.insert(0, initial_text if initial_text else "Testo di esempio")
        self.entry_text.bind("<KeyRelease>", self._update_preview)

        # -------------------------------------------------------------
        # SECTION 3: FONT SELECTION & FORMATTING CONTROLS
        # -------------------------------------------------------------
        font_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8)
        font_frame.pack(fill="x", padx=20, pady=6)

        # Row 1: Font Family & Size
        row1 = ctk.CTkFrame(font_frame, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(8, 4))

        lbl_fam = ctk.CTkLabel(row1, text="Carattere:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_fam.pack(side="left", padx=(0, 6))

        self.menu_font = ctk.CTkOptionMenu(
            row1,
            values=FONT_FAMILIES,
            command=self._on_font_changed,
            width=180
        )
        self.menu_font.set(self.font_family)
        self.menu_font.pack(side="left", padx=4)

        lbl_sz = ctk.CTkLabel(row1, text="Dimensione:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_sz.pack(side="left", padx=(15, 6))

        self.slider_size = ctk.CTkSlider(
            row1,
            from_=8,
            to=48,
            number_of_steps=40,
            width=120,
            command=self._on_size_slider
        )
        self.slider_size.set(self.font_size)
        self.slider_size.pack(side="left", padx=4)

        self.lbl_size_val = ctk.CTkLabel(row1, text=f"{self.font_size} pt", font=ctk.CTkFont(size=12, weight="bold"), width=45)
        self.lbl_size_val.pack(side="left", padx=2)

        # Row 2: Style (Bold / Italic) & Color
        row2 = ctk.CTkFrame(font_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 8))

        lbl_st = ctk.CTkLabel(row2, text="Stile:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_st.pack(side="left", padx=(0, 6))

        self.bold_var = tk.BooleanVar(value=self.font_bold)
        self.chk_bold = ctk.CTkCheckBox(row2, text="Grassetto (Bold)", variable=self.bold_var, command=self._update_preview)
        self.chk_bold.pack(side="left", padx=6)

        self.italic_var = tk.BooleanVar(value=self.font_italic)
        self.chk_italic = ctk.CTkCheckBox(row2, text="Corsivo (Italic)", variable=self.italic_var, command=self._update_preview)
        self.chk_italic.pack(side="left", padx=6)

        lbl_col = ctk.CTkLabel(row2, text="Colore:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_col.pack(side="left", padx=(15, 6))

        # Color picker button
        self.btn_color_chip = ctk.CTkButton(
            row2,
            text="",
            width=30,
            height=26,
            fg_color=self.text_color,
            hover_color=self.text_color,
            border_width=2,
            border_color="#ffffff",
            command=self._choose_custom_color
        )
        self.btn_color_chip.pack(side="left", padx=4)

        # Quick color chips
        for name, hx in COLOR_PALETTE[:4]:
            btn = ctk.CTkButton(
                row2,
                text="",
                width=22,
                height=22,
                fg_color=hx,
                hover_color=hx,
                corner_radius=11,
                command=lambda c=hx: self._set_color(c)
            )
            btn.pack(side="left", padx=2)

        # -------------------------------------------------------------
        # SECTION 4: LIVE PREVIEW
        # -------------------------------------------------------------
        preview_card = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=8, border_width=1, border_color="#cbd5e1")
        preview_card.pack(fill="both", expand=True, padx=20, pady=8)

        self.preview_canvas = tk.Canvas(preview_card, bg="#ffffff", bd=0, highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

        # -------------------------------------------------------------
        # SECTION 5: ACTION BAR
        # -------------------------------------------------------------
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=20, pady=(4, 14))

        btn_cancel = ctk.CTkButton(
            bottom,
            text="Annulla",
            fg_color="#334155",
            hover_color="#475569",
            width=100,
            command=self.destroy
        )
        btn_cancel.pack(side="left")

        btn_confirm = ctk.CTkButton(
            bottom,
            text="✅ Inserisci nel PDF",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=38,
            command=self._confirm_insert
        )
        btn_confirm.pack(side="right")

        self.after(100, self._update_preview)

    def _apply_detected_font(self, f_info: Dict[str, Any]):
        fam = f_info.get("family", "Arial")
        dom_size = int(f_info.get("dominant_size", 12))
        col = f_info.get("color", "#000000")
        is_b = f_info.get("bold", False)
        is_i = f_info.get("italic", False)

        if fam in FONT_FAMILIES:
            self.font_family = fam
            self.menu_font.set(fam)

        self.font_size = dom_size
        self.slider_size.set(dom_size)
        self.lbl_size_val.configure(text=f"{dom_size} pt")

        self.bold_var.set(is_b)
        self.italic_var.set(is_i)
        self._set_color(col)

        self.lbl_feedback.configure(text=f"✓ Applicato stile: {fam} ({dom_size} pt)", text_color="#10b981")
        self._update_preview()

    def _on_font_changed(self, choice):
        self.font_family = choice
        self._update_preview()

    def _on_size_slider(self, val):
        self.font_size = int(val)
        self.lbl_size_val.configure(text=f"{self.font_size} pt")
        self._update_preview()

    def _set_color(self, hex_color):
        self.text_color = hex_color
        self.btn_color_chip.configure(fg_color=hex_color, hover_color=hex_color)
        self._update_preview()

    def _choose_custom_color(self):
        col = colorchooser.askcolor(color=self.text_color, title="Scegli Colore Inchiostro")
        if col and col[1]:
            self._set_color(col[1])

    def _update_preview(self, event=None):
        txt = self.entry_text.get()
        if not txt:
            txt = "Anteprima testo"

        self.font_bold = self.bold_var.get()
        self.font_italic = self.italic_var.get()

        styles = []
        if self.font_bold: styles.append("bold")
        if self.font_italic: styles.append("italic")
        style_str = " ".join(styles) if styles else "normal"

        tk_font = (self.font_family, min(36, max(10, self.font_size)), style_str)

        self.preview_canvas.delete("all")
        cw = max(50, self.preview_canvas.winfo_width())
        ch = max(50, self.preview_canvas.winfo_height())

        base_y = ch // 2 + 10
        self.preview_canvas.create_line(20, base_y, cw - 20, base_y, dash=(3, 3), fill="#e2e8f0")

        self.preview_canvas.create_text(
            cw // 2, ch // 2,
            text=txt,
            font=tk_font,
            fill=self.text_color,
            anchor="center"
        )

    def _confirm_insert(self):
        txt = self.entry_text.get().strip()
        if not txt:
            return
        if self.callback:
            self.callback(
                text=txt,
                font_family=self.font_family,
                font_size=float(self.font_size),
                font_bold=self.bold_var.get(),
                font_italic=self.italic_var.get(),
                color=self.text_color
            )
        self.destroy()
