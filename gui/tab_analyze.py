import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate

TAB_BG  = '#ffffff'
ACCENT  = '#2563eb'

# Report colour tags
T_HEADER     = ('section_header',  '#1e293b', ('Segoe UI', 11, 'bold'))
T_SEP        = ('separator',       '#cbd5e1', ('Courier', 9))
T_META_KEY   = ('meta_key',        '#64748b', ('Segoe UI', 10))
T_META_VAL   = ('meta_val',        '#1e293b', ('Segoe UI', 10, 'bold'))
T_CKT_NUM    = ('circuit_num',     '#2563eb', ('Segoe UI', 10, 'bold'))
T_CKT_NAME  = ('circuit_name',    '#1d4ed8', ('Segoe UI', 10, 'bold'))
T_LBL        = ('label',           '#94a3b8', ('Segoe UI', 9))
T_COMP       = ('comp_ref',        '#059669', ('Courier', 10, 'bold'))
T_NODE       = ('node_ref',        '#7c3aed', ('Courier', 10))
T_UNC_HEAD   = ('unc_header',      '#dc2626', ('Segoe UI', 10, 'bold'))
T_UNC_REF    = ('unc_ref',         '#dc2626', ('Courier', 10))


class TabAnalyze:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, style='Tab.TFrame')
        self._file_path = tk.StringVar()
        self._report_content = ''
        self._build()
        self._setup_drag_drop()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        pad = dict(padx=16, pady=8)

        # ── File picker row
        picker = ttk.Frame(self.frame, style='Tab.TFrame')
        picker.pack(fill='x', **pad)

        ttk.Label(picker, text='Fichier netlist :',
                  style='Tab.TLabel').pack(side='left')

        entry = ttk.Entry(picker, textvariable=self._file_path, width=55)
        entry.pack(side='left', padx=(8, 6))
        entry.bind('<Double-Button-1>', lambda _: self._browse())

        ttk.Button(picker, text='Parcourir',
                   style='Secondary.TButton',
                   command=self._browse).pack(side='left')

        ttk.Button(picker, text='  ▶  Analyser',
                   command=self._analyze).pack(side='left', padx=(10, 0))

        # ── Stats bar (hidden until first analysis)
        self._stats_frame = tk.Frame(self.frame, bg='#f8fafc',
                                     relief='flat', bd=0)
        self._stats_frame.pack(fill='x', padx=16)
        self._stat_total = self._make_stat(self._stats_frame, '—', 'Composants')
        self._stat_groups = self._make_stat(self._stats_frame, '—', 'Groupes identifiés')
        self._stat_pct    = self._make_stat(self._stats_frame, '—', '% classifiés')
        self._stats_frame.pack_forget()   # hide initially

        # ── Report area
        report_outer = ttk.Frame(self.frame, style='Tab.TFrame')
        report_outer.pack(fill='both', expand=True, padx=16, pady=(0, 4))

        self._text = tk.Text(
            report_outer,
            state='disabled', wrap='none',
            font=('Courier', 10),
            bg='#f8fafc', fg='#1e293b',
            relief='flat', bd=0,
            selectbackground='#bfdbfe',
            padx=10, pady=10,
            cursor='arrow',
        )
        sb_y = ttk.Scrollbar(report_outer, orient='vertical',
                              command=self._text.yview)
        sb_x = ttk.Scrollbar(report_outer, orient='horizontal',
                              command=self._text.xview)
        self._text.configure(yscrollcommand=sb_y.set,
                              xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        self._text.pack(side='left', fill='both', expand=True)
        self._setup_tags()

        # ── Bottom buttons
        btns = ttk.Frame(self.frame, style='Tab.TFrame')
        btns.pack(fill='x', padx=16, pady=(0, 12))
        ttk.Button(btns, text='💾  Sauvegarder le rapport',
                   style='Secondary.TButton',
                   command=self._save).pack(side='left')
        ttk.Button(btns, text='📋  Copier',
                   style='Secondary.TButton',
                   command=self._copy).pack(side='left', padx=8)

        # ── Drop zone hint
        self._drop_label = ttk.Label(
            self.frame,
            text='  ↓  Glissez un fichier .txt ici  ↓',
            style='Tab.TLabel',
            foreground='#94a3b8',
        )

    def _make_stat(self, parent, value, label):
        f = tk.Frame(parent, bg='#f8fafc')
        f.pack(side='left', padx=24, pady=6)
        val_lbl = tk.Label(f, text=value, bg='#f8fafc',
                           font=('Segoe UI', 22, 'bold'), fg=ACCENT)
        val_lbl.pack()
        tk.Label(f, text=label, bg='#f8fafc',
                 font=('Segoe UI', 9), fg='#64748b').pack()
        return val_lbl

    def _setup_tags(self):
        for tag, color, font in [T_HEADER, T_SEP, T_META_KEY, T_META_VAL,
                                  T_CKT_NUM, T_CKT_NAME, T_LBL,
                                  T_COMP, T_NODE, T_UNC_HEAD, T_UNC_REF]:
            self._text.tag_configure(tag, foreground=color, font=font)

    # ── Drag & drop ─────────────────────────────────────────────────────────

    def _setup_drag_drop(self):
        try:
            self.frame.winfo_toplevel().drop_target_register('DND_Files')  # type: ignore
            self.frame.winfo_toplevel().dnd_bind('<<Drop>>', self._on_drop)   # type: ignore
        except Exception:
            pass

    def _on_drop(self, event):
        path = event.data.strip('{}')
        self._file_path.set(path)
        self._analyze()

    # ── Actions ─────────────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title='Choisir un fichier netlist',
            filetypes=[('Fichiers texte', '*.txt'), ('Tous les fichiers', '*.*')],
        )
        if path:
            self._file_path.set(path)

    def _analyze(self):
        path = self._file_path.get().strip()
        if not path:
            self._show_error('Veuillez sélectionner un fichier circuit.')
            return
        try:
            comps   = parse_file(path)
            graph   = build_graph(comps)
            results = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report   = generate(results, path, len(comps),
                                all_refs=all_refs)
            self._report_content = report

            # Stats
            total      = len(comps)
            groups     = len(results)
            classified = sum(len(r['components']) for r in results)
            pct        = int(100 * classified / total) if total else 0

            self._stat_total.config(text=str(total))
            self._stat_groups.config(text=str(groups))
            self._stat_pct.config(
                text=f'{pct}%',
                fg='#16a34a' if pct >= 80 else '#ea580c' if pct >= 60 else '#dc2626',
            )
            self._stats_frame.pack(fill='x', padx=16, before=self._text.master)

            self._render_report(report)

        except FileNotFoundError:
            self._show_error(f'Fichier introuvable :\n{path}')
        except ValueError as e:
            self._show_error(f'Erreur netlist :\n{e}')
        except Exception as e:
            self._show_error(f'Erreur lors de l\'analyse :\n{e}')

    def _save(self):
        if not self._report_content:
            messagebox.showinfo('Information', 'Aucun rapport à sauvegarder.')
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Fichiers texte', '*.txt')],
            title='Sauvegarder le rapport',
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._report_content)
            messagebox.showinfo('Succès', f'Rapport sauvegardé :\n{path}')

    def _copy(self):
        if not self._report_content:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(self._report_content)
        messagebox.showinfo('Copié', 'Rapport copié dans le presse-papiers.')

    # ── Rendering ───────────────────────────────────────────────────────────

    def _show_error(self, msg: str):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        self._text.insert('1.0', msg, T_UNC_HEAD[0])
        self._text.configure(state='disabled')

    def _render_report(self, text: str):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')

        in_unclassified = False
        for raw_line in text.splitlines():
            line = raw_line

            # Section header ===
            if line.startswith('==='):
                self._insert(line + '\n', T_HEADER[0])
                in_unclassified = False

            # Separator ---
            elif set(line.strip()) == {'-'} and len(line.strip()) > 4:
                self._insert(line + '\n', T_SEP[0])

            # Circuit entry [N] Name
            elif line.strip() and line.strip()[0] == '[':
                bracket_end = line.index(']') + 1
                self._insert(line[:bracket_end], T_CKT_NUM[0])
                self._insert(line[bracket_end:] + '\n', T_CKT_NAME[0])
                in_unclassified = False

            # Composants : ref1, ref2, ...
            elif '    Composants :' in line:
                colon_pos = line.index(':') + 1
                self._insert(line[:colon_pos], T_LBL[0])
                self._render_refs(line[colon_pos:])
                self._insert('\n', '')

            # Nœuds : net1 → net2
            elif '    Nœuds' in line:
                colon_pos = line.index(':') + 1
                self._insert(line[:colon_pos], T_LBL[0])
                self._insert(line[colon_pos:] + '\n', T_NODE[0])

            # Fichier / totaux / groupes meta lines
            elif any(k in line for k in ('Fichier', 'Composants totaux', 'Groupes identifiés')):
                if ':' in line:
                    colon_pos = line.index(':') + 1
                    self._insert(line[:colon_pos], T_META_KEY[0])
                    self._insert(line[colon_pos:] + '\n', T_META_VAL[0])
                else:
                    self._insert(line + '\n', '')

            # Unclassified header
            elif 'non classifiés' in line:
                self._insert(line + '\n', T_UNC_HEAD[0])
                in_unclassified = True

            # Unclassified refs (indented line after header)
            elif in_unclassified and line.startswith('    '):
                self._insert(line + '\n', T_UNC_REF[0])

            else:
                self._insert(line + '\n', '')

        self._text.configure(state='disabled')
        self._text.see('1.0')

    def _insert(self, text: str, tag: str):
        self._text.insert('end', text, tag if tag else ())

    def _render_refs(self, refs_str: str):
        """Colour each component ref individually."""
        parts = refs_str.split(',')
        for i, part in enumerate(parts):
            ref = part.strip()
            if ref:
                self._insert(' ' + ref, T_COMP[0])
                if i < len(parts) - 1:
                    self._insert(',', T_LBL[0])
