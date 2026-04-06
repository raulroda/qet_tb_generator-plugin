#!/usr/bin/env python3
# encoding: utf-8

import logging as log
import os
import re
import shutil
import sys
import json
import time
from PIL import Image
from functools import cmp_to_key
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from .qetproject import QETProject
    from .terminalblock import TerminalBlock
except ImportError:
    from qetproject import QETProject
    from terminalblock import TerminalBlock

# --- CONSTANTS ---
VERSION = '2.0.2'
TITLE = 'QET Terminal Block Generator - v{} (CustomTkinter)'.format(VERSION)
CONFIG_FILE = 'qet_tb_generator.json'
DEBUG_MODE = False  # Set to True to enable bridge_debug.txt logging

TABLE = [
    {'col':0, 'text':'ORDER', 'size':80, 'edit': False, 'key': 'order'},
    {'col':1, 'text':'POS.', 'size':50, 'edit': False, 'key': 'terminal_pos'},
    {'col':2 , 'text':'BLOCK', 'size':80, 'edit': False, 'key': 'block_name'},
    {'col':3 , 'text':'ID', 'size':70, 'edit': False, 'key': 'terminal_name'},
    {'col':4 , 'text':'ETAGE', 'size':60, 'edit': False, 'key': 'etage'},
    {'col':5 , 'text':'XREF', 'size':80, 'edit': False, 'key': 'terminal_xref'},
    {'col':6 , 'text':'CABLE', 'size':90, 'edit': False, 'key': 'cable'},
    {'col':7 , 'text':'B1', 'size':30, 'edit': False, 'key': 'bridge1'},
    {'col':8 , 'text':'B2', 'size':30, 'edit': False, 'key': 'bridge2'},
    {'col':9 , 'text':'B3', 'size':30, 'edit': False, 'key': 'bridge3'},
    {'col':10, 'text':'B4', 'size':30, 'edit': False, 'key': 'bridge4'},
    {'col':11, 'text':'TYPE', 'size':100, 'edit': False, 'key': 'terminal_type'},
    {'col':12, 'text':'HOSE', 'size':120, 'edit': True, 'key': 'hose'},
    {'col':13, 'text':'CONDUCTOR', 'size':100, 'edit': True, 'key': 'conductor'},
    {'col':14, 'text':'COLOR', 'size':120, 'edit': False, 'key': 'terminal_color'}
]

HELP = """
Terminal Block generator plug-in for QElectrotech
https://qelectrotech.org/

Steps:
  - In QET, optional: Choose Project> Clean Project.
  - In QET: Close and reopen the project.
  - In this plug-in: Edit the terminals info.
  - In this plug-in: Press the 'CREATE TERMINAL BLOCKS' button.
  - In QET: Reopen the project.
  - In QET: Under the 'COLLECTIONS' tree of the project, all the terminal blocks appear.

Considerations:
  - This addon searches all elements of type 'Terminal'.
  - Terminals must have a tag like X1:1.
  - All terminals with same <terminal_block_name> are grouped.

Created by raulroda8@gmail.com
Refactored to CustomTkinter by Antigravity
"""

# Natural sort for IDs
def natural_sort_key(s):
    if not s: return []
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', str(s))]

class TerminalRow:
    def __init__(self, master, app, terminal_data, on_change_callback, move_up_cb, move_down_cb):
        self.master = master
        self.app = app # Direct reference to App
        self.data = terminal_data # Reference for real-time sync
        self.on_change = on_change_callback
        self.widgets = {}
        
        # Row Frame
        self.frame = ctk.CTkFrame(master)
        self.frame.pack(fill="x", padx=2, pady=1)

        # Order Buttons
        btn_frame = ctk.CTkFrame(self.frame, width=80, height=25, fg_color="transparent")
        btn_frame.pack(side="left", padx=2)
        btn_frame.pack_propagate(False)
        
        self.up_btn = ctk.CTkButton(btn_frame, text="▲", width=30, height=20, command=lambda: move_up_cb(self))
        self.up_btn.pack(side="left", padx=1)
        self.dw_btn = ctk.CTkButton(btn_frame, text="▼", width=30, height=20, command=lambda: move_down_cb(self))
        self.dw_btn.pack(side="left", padx=1)

        # Columns
        for col_def in TABLE[1:]:
            key = col_def['key']
            val = self.data.get(key, "")
            
            if key.startswith('bridge'):
                # CustomTkinter CTkButton doesn't support textvariable. 
                w = ctk.CTkButton(self.frame, text=val if val else "", width=col_def['size'], height=25, 
                                  command=lambda k=key: self.toggle_bridge(k))
                w.pack(side="left", padx=2)
                self.widgets[key] = w
            elif key == 'etage':
                w = ctk.CTkButton(self.frame, text=val if val else "1", width=col_def['size'], height=25, 
                                  command=self.toggle_etage)
                w.pack(side="left", padx=2)
                self.widgets[key] = w
            elif key == 'terminal_type':
                w = ctk.CTkOptionMenu(self.frame, values=["STANDARD", "GROUND", "FUSE"], 
                                      width=col_def['size'], height=25,
                                      command=lambda v, k=key: self.update_data(k, v))
                w.set(val if val else "STANDARD")
                w.pack(side="left", padx=2)
                self.widgets[key] = w
            elif key == 'terminal_color':
                w = ctk.CTkFrame(self.frame, width=col_def['size'], height=25, fg_color="transparent")
                w.pack(side="left", padx=2)
                w.pack_propagate(False)
                self.color_widgets = {}
                colors = [
                    ("orange", "#FFA500"),
                    ("lightblue", "#ADD8E6"),
                    ("red", "#FF0000"),
                    ("darkblue", "#00008B"),
                    ("green", "#008000")
                ]
                for c_name, c_hex in colors:
                    cb = ctk.CTkButton(w, text="", width=18, height=18, fg_color=c_hex, hover_color=c_hex,
                                       border_width=1, border_color="white",
                                       command=lambda cn=c_name: self.set_color(cn))
                    cb.pack(side="left", padx=2, pady=3)
                    self.color_widgets[c_name] = cb
                self.widgets[key] = w
                self.update_color_selection(val)
            elif col_def['edit']:
                w = ctk.CTkEntry(self.frame, width=col_def['size'], height=25)
                w.insert(0, val)
                w.bind("<KeyRelease>", lambda e, k=key, obj=w: self.update_data(k, obj.get()))
                w.bind("<FocusOut>", lambda e, k=key, obj=w: self.update_data(k, obj.get()))
                # Removed local Control-v to use global handler
                w.bind("<Button-1>", lambda e, k=key: self.app.on_cell_click(e, self, k))
                w.pack(side="left", padx=2)
                self.widgets[key] = w
            else:
                w = ctk.CTkLabel(self.frame, text=val, width=col_def['size'], height=25)
                w.pack(side="left", padx=2)
                self.widgets[key] = w

    def toggle_etage(self):
        try:
            key = 'etage'
            btn = self.widgets[key]
            current = str(btn.cget("text")).strip()
            
            # 1 -> 2 -> 3 -> 4 -> 1
            mapping = {"1": "2", "2": "3", "3": "4", "4": "1"}
            new_val = mapping.get(current, "1")
            
            btn.configure(text=new_val)
            self.data[key] = new_val
            
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"ETAGE LOG: TB={self.data.get('block_name')} T={self.data.get('terminal_name')} -> '{new_val}'\n")
            
            self.on_change(self.data.get('block_name', ''))
        except Exception:
            pass

    def toggle_bridge(self, key):
        try:
            btn = self.widgets[key]
            current = str(btn.cget("text")).strip().upper()
            
            # Logic: "" -> "O" -> "F" -> ""
            if current == "":
                new_val = "O"
            elif current == "O":
                new_val = "F"
            else:
                new_val = ""
            
            # 1. Update UI button text
            btn.configure(text=new_val)
            
            # 2. Update the dictionary directly (it's a reference to the project master list)
            self.data[key] = new_val
            
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"CLIC LOG: TB={self.data.get('block_name')} T={self.data.get('terminal_name')} {key} -> '{new_val}'\n")
            
            # 4. Mark as edited
            self.on_change(self.data.get('block_name', ''))
            
        except Exception as e:
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"CRITICAL ERROR in toggle_bridge: {str(e)}\n")

    def update_data(self, key, value):
        self.data[key] = value
        self.on_change(self.data['block_name'])



    def set_color(self, color_name):
        if self.data.get('terminal_color') == color_name:
            self.data['terminal_color'] = ""
        else:
            self.data['terminal_color'] = color_name
        self.update_color_selection(self.data['terminal_color'])
        self.on_change(self.data['block_name'])

    def update_color_selection(self, selected_color):
        if not hasattr(self, 'color_widgets'): return
        for c_name, cb in self.color_widgets.items():
            if c_name == selected_color:
                cb.configure(border_width=3, border_color="black")
            else:
                cb.configure(border_width=1, border_color="white")

    def get_data(self):
        # Ensure latest data from entries/OptionMenus
        for key, widget in self.widgets.items():
            try:
                if isinstance(widget, ctk.CTkEntry):
                    val = widget.get()
                    self.data[key] = val
                elif isinstance(widget, ctk.CTkOptionMenu):
                    self.data[key] = widget.get()
            except Exception:
                pass
        return self.data

    def update_ui(self, new_data):
        self.data = new_data # Keep the original reference
        for key, widget in self.widgets.items():
            val = self.data.get(key, "")
            if key.startswith('bridge'):
                widget.configure(text=val if val else "")
            elif key == 'etage':
                widget.configure(text=val if val else "1")
            elif key == 'terminal_type':
                widget.set(val if val else "STANDARD")
            elif isinstance(widget, ctk.CTkEntry):
                # Only update if the value has changed or focus is lost to prevent focus jumping
                if widget.get() != val:
                    widget.delete(0, tk.END)
                    widget.insert(0, val)
            elif isinstance(widget, ctk.CTkLabel):
                if widget.cget("text") != val:
                    widget.configure(text=val)
            elif isinstance(widget, ctk.CTkOptionMenu):
                if widget.get() != val:
                    widget.set(val if val else "STANDARD")
            elif key == 'terminal_color':
                self.update_color_selection(val)

class App(ctk.CTk):
    def __init__(self, qet_file):
        super().__init__()
        
        self.qet_file = qet_file
        self.qet_project = QETProject(qet_file)
        self.edited_terminals = []
        self.rows = []
        self.settings = {}
        self.selected_cells = set() # Set of (terminal_uuid, key)
        self.last_clicked_cell = None # (terminal_uuid, key)

        # Initialiser le fichier de debug pour cette session
        if DEBUG_MODE:
            try:
                with open("bridge_debug.txt", "w") as f:
                    f.write(f"--- SESSION START ---\nTime: {time.ctime()}\n")
            except: pass

        self.title(TITLE)
        # Maximize window on startup
        self.after(0, lambda: self.state('zoomed'))
        ctk.set_appearance_mode("dark")
        
        self.setup_ui()
        self.load_settings()
        self.refresh_table()

        # Global Paste Handling
        self.bind_all("<Control-v>", self.handle_global_paste)
        self.bind_all("<Control-V>", self.handle_global_paste)

    def setup_ui(self):
        # Grid layout
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Content
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="QET Plugin", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20)

        # Filter List
        self.filter_label = ctk.CTkLabel(self.sidebar, text="Filter Terminal Blocks:")
        self.filter_label.pack(pady=(10, 0))

        self.tb_scroll = ctk.CTkScrollableFrame(self.sidebar, height=200)
        self.tb_scroll.pack(fill="x", padx=10, pady=5)
        self.tb_buttons = {}
        self.selected_tbs = set(["-- ALL --"])
        self.update_tb_list()

        # Action Buttons
        self.sort_btn = ctk.CTkButton(self.sidebar, text="Sort by ID", command=self.sort_by_id)
        self.sort_btn.pack(pady=10, padx=20)

        self.create_btn = ctk.CTkButton(self.sidebar, text="Create Terminal Blocks", fg_color="green", hover_color="darkgreen", command=self.on_create)
        self.create_btn.pack(pady=10, padx=20)

        self.settings_btn = ctk.CTkButton(self.sidebar, text="Paramètres", command=self.open_settings)
        self.settings_btn.pack(pady=10, padx=20)

        self.help_btn = ctk.CTkButton(self.sidebar, text="Help", command=lambda: messagebox.showinfo("Help", HELP))
        self.help_btn.pack(side="bottom", pady=20, padx=20)

        # Auto-Fill Section
        self.autofill_label = ctk.CTkLabel(self.sidebar, text="Auto-Fill Conductors:", font=ctk.CTkFont(weight="bold"))
        self.autofill_label.pack(pady=(20, 0))

        self.btn_brown = ctk.CTkButton(self.sidebar, text="24V -> Brown", fg_color="#8B4513", hover_color="#5D2E0D", 
                                      command=lambda: self.apply_auto_fill("24V", "Brown"))
        self.btn_brown.pack(pady=5, padx=20)

        self.btn_blue = ctk.CTkButton(self.sidebar, text="0V -> Blue", fg_color="#0000FF", hover_color="#00008B", 
                                     command=lambda: self.apply_auto_fill("0V", "Blue"))
        self.btn_blue.pack(pady=5, padx=20)

        self.btn_noir1 = ctk.CTkButton(self.sidebar, text="Others -> Black", fg_color="#333333", hover_color="#000000", 
                                      command=lambda: self.apply_auto_fill("OTHERS", "Black"))
        self.btn_noir1.pack(pady=5, padx=20)

        self.btn_reset = ctk.CTkButton(self.sidebar, text="Réinitialiser Conductor", fg_color="#FF4C4C", hover_color="#CC0000", 
                                      command=lambda: self.apply_auto_fill("RESET", ""))
        self.btn_reset.pack(pady=5, padx=20)

        # Bridge Generation Section
        self.bridge_label = ctk.CTkLabel(self.sidebar, text="Générer les Ponts:", font=ctk.CTkFont(weight="bold"))
        self.bridge_label.pack(pady=(20, 0))

        self.bridge_btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.bridge_btn_frame.pack(pady=5, padx=20)
        
        for i in range(1, 5):
            btn = ctk.CTkButton(self.bridge_btn_frame, text=f"B{i}", width=40, height=30,
                                command=lambda x=i: self.apply_auto_bridge(x))
            btn.pack(side="left", padx=2)

        # Content Area
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Header
        self.header_frame = ctk.CTkFrame(self.content, height=30)
        self.header_frame.pack(fill="x", padx=2, pady=(0, 5))
        for col_def in TABLE:
            lbl = ctk.CTkLabel(self.header_frame, text=col_def['text'], width=col_def['size'], font=ctk.CTkFont(weight="bold"))
            lbl.pack(side="left", padx=2)

        # Scrollable Table
        self.scroll_frame = ctk.CTkScrollableFrame(self.content)
        self.scroll_frame.pack(fill="both", expand=True)

    def update_tb_list(self):
        names = ["-- ALL --"] + self.qet_project.tb_names
        
        # Check if we need to rebuild the list (if names changed)
        if set(self.tb_buttons.keys()) != set(names):
            for btn in self.tb_buttons.values():
                btn.destroy()
            self.tb_buttons = {}
            for name in names:
                btn = ctk.CTkButton(self.tb_scroll, text=name, height=25, 
                                    command=lambda n=name: self.toggle_tb_filter(n))
                btn.pack(fill="x", pady=1)
                self.tb_buttons[name] = btn
        
        # Sync styles
        for name, btn in self.tb_buttons.items():
            is_sel = name in self.selected_tbs
            btn.configure(
                fg_color="blue" if is_sel else "transparent",
                text_color="white" if is_sel else ["#000000", "#FFFFFF"]
            )

    def toggle_tb_filter(self, name):
        if name == "-- ALL --":
            self.selected_tbs = set(["-- ALL --"])
        else:
            if "-- ALL --" in self.selected_tbs:
                self.selected_tbs.remove("-- ALL --")
            if name in self.selected_tbs:
                self.selected_tbs.remove(name)
            else:
                self.selected_tbs.add(name)
            if not self.selected_tbs:
                self.selected_tbs.add("-- ALL --")
        
        self.update_tb_list()
        self.refresh_table()

    def refresh_table(self):
        # Sync Entry values to data BEFORE swapping widget data (prevents data loss)
        for row in self.rows:
            row.get_data()
        
        # Filter terminals
        show_all = "-- ALL --" in self.selected_tbs
        target_terminals = [t for t in self.qet_project.terminals 
                           if show_all or t['block_name'] in self.selected_tbs]
        
        # Widget pooling: reuse existing rows, create new ones only if needed
        num_needed = len(target_terminals)
        num_existing = len(self.rows)
        
        # Update existing rows with new data
        for i in range(min(num_needed, num_existing)):
            self.rows[i].update_ui(target_terminals[i])
            self.rows[i].frame.pack(fill="x", padx=2, pady=1)
        
        # Create additional rows if needed
        for i in range(num_existing, num_needed):
            row = TerminalRow(self.scroll_frame, self, target_terminals[i], 
                            self.mark_as_edited, self.move_up, self.move_down)
            self.rows.append(row)
        
        # Hide excess rows (don't destroy, keep for reuse)
        for i in range(num_needed, num_existing):
            self.rows[i].frame.pack_forget()
        
        self.apply_selection_visuals()

    def on_cell_click(self, event, row_obj, key):
        curr_uuid = row_obj.data.get('uuid')
        if not curr_uuid: return

        # Determine modifiers (state bits: 0x1=Shift, 0x4=Control)
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0
        
        if not ctrl and not shift:
            # Simple click: select only this cell if not already part of a selection
            if (curr_uuid, key) not in self.selected_cells:
                self.selected_cells = {(curr_uuid, key)}
        elif ctrl:
            # Toggle cell
            if (curr_uuid, key) in self.selected_cells:
                self.selected_cells.remove((curr_uuid, key))
            else:
                self.selected_cells.add((curr_uuid, key))
        elif shift and self.last_clicked_cell and self.last_clicked_cell[1] == key:
            # Range selection in same column
            try:
                # Find indices by UUID
                all_uuids = [r.data.get('uuid') for r in self.rows]
                idx1 = all_uuids.index(self.last_clicked_cell[0])
                idx2 = all_uuids.index(curr_uuid)
                start, end = min(idx1, idx2), max(idx1, idx2)
                for i in range(start, end + 1):
                    u = self.rows[i].data.get('uuid')
                    if u: self.selected_cells.add((u, key))
            except ValueError:
                pass

        self.last_clicked_cell = (curr_uuid, key)
        self.apply_selection_visuals()

    def apply_selection_visuals(self):
        for row in self.rows:
            u = row.data.get('uuid')
            for key, widget in row.widgets.items():
                if isinstance(widget, ctk.CTkEntry):
                    if (u, key) in self.selected_cells:
                        widget.configure(fg_color="#3B5D61", border_color="#00FFFF", border_width=2)
                    else:
                        widget.configure(fg_color=["#F9F9FA", "#343638"], border_color=["#979da2", "#565b5e"], border_width=2)

    def mark_as_edited(self, tb_name):
        if tb_name not in self.edited_terminals:
            self.edited_terminals.append(tb_name)

    def sort_by_id(self):
        # Sort terminals within each block and re-assign physical positions
        
        # 1. Group by block
        blocks = {}
        for t in self.qet_project.terminals:
            bn = t['block_name']
            if bn not in blocks:
                blocks[bn] = []
            blocks[bn].append(t)
            
        # 2. Sort each block by terminal_name and re-assign POS
        new_terminals = []
        # Keep original block order
        sorted_block_names = []
        for t in self.qet_project.terminals:
            if t['block_name'] not in sorted_block_names:
                sorted_block_names.append(t['block_name'])
                
        for bn in sorted_block_names:
            group = blocks[bn]
            
            def special_sort_key(t):
                # 1. Primary: Terminal Name (Natural Sort)
                name_key = natural_sort_key(t['terminal_name'])
                
                # 2. Secondary: Cable content priority
                cable = str(t.get('cable', '')).upper()
                if "0V" in cable:
                    priority = 0
                elif "24V" in cable:
                    priority = 1
                else:
                    priority = 2
                
                return (name_key, priority)

            group.sort(key=special_sort_key)
            
            # Re-assign positions 1, 2, 3...
            for i, t in enumerate(group):
                t['terminal_pos'] = i + 1
            
            new_terminals.extend(group)
            
        self.qet_project.terminals[:] = new_terminals
        self.refresh_table()

    def move_up(self, row_obj):
        try:
            u_curr = row_obj.data.get('uuid')
            t_name = row_obj.data.get('terminal_name')
            
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"\n--- MOVE UP REQUEST: Terminal {t_name} ---\n")

            # 1. Get currently displayed order
            show_all = "-- ALL --" in self.selected_tbs
            displayed = [t for t in self.qet_project.terminals 
                        if show_all or t['block_name'] in self.selected_tbs]
            
            # 2. Find position in view
            d_idx = next((i for i, t in enumerate(displayed) if t.get('uuid') == u_curr), -1)
            
            if d_idx <= 0:
                return

            u_prev = displayed[d_idx-1].get('uuid')
            
            # 3. Swap in master list
            all_t = self.qet_project.terminals
            m_idx_curr = next((i for i, t in enumerate(all_t) if t.get('uuid') == u_curr), -1)
            m_idx_prev = next((i for i, t in enumerate(all_t) if t.get('uuid') == u_prev), -1)

            if m_idx_curr != -1 and m_idx_prev != -1:
                # Same block restriction
                if all_t[m_idx_curr]['block_name'] == all_t[m_idx_prev]['block_name']:
                    # Swap ALL data except pos/block
                    keys_to_swap = [col['key'] for col in TABLE[3:]]
                    for k in keys_to_swap:
                        v_curr = all_t[m_idx_curr].get(k, '')
                        v_prev = all_t[m_idx_prev].get(k, '')
                        all_t[m_idx_curr][k] = v_prev
                        all_t[m_idx_prev][k] = v_curr
                    
                    # Swap identity markers
                    all_t[m_idx_curr]['uuid'], all_t[m_idx_prev]['uuid'] = all_t[m_idx_prev]['uuid'], all_t[m_idx_curr]['uuid']
                    
                    self.mark_as_edited(all_t[m_idx_curr]['block_name'])
                    self.refresh_table()
        except Exception as e:
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f: f.write(f"  CRITICAL ERROR move_up: {e}\n")

    def move_down(self, row_obj):
        try:
            u_curr = row_obj.data.get('uuid')
            t_name = row_obj.data.get('terminal_name')

            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"\n--- MOVE DOWN REQUEST: Terminal {t_name} ---\n")

            show_all = "-- ALL --" in self.selected_tbs
            displayed = [t for t in self.qet_project.terminals 
                        if show_all or t['block_name'] in self.selected_tbs]
            
            d_idx = next((i for i, t in enumerate(displayed) if t.get('uuid') == u_curr), -1)
            
            if d_idx == -1 or d_idx >= len(displayed) - 1:
                return

            u_next = displayed[d_idx+1].get('uuid')
            
            all_t = self.qet_project.terminals
            m_idx_curr = next((i for i, t in enumerate(all_t) if t.get('uuid') == u_curr), -1)
            m_idx_next = next((i for i, t in enumerate(all_t) if t.get('uuid') == u_next), -1)

            if m_idx_curr != -1 and m_idx_next != -1:
                if all_t[m_idx_curr]['block_name'] == all_t[m_idx_next]['block_name']:
                    # Swap ALL data except pos/block
                    keys_to_swap = [col['key'] for col in TABLE[3:]]
                    for k in keys_to_swap:
                        v_curr = all_t[m_idx_curr].get(k, '')
                        v_next = all_t[m_idx_next].get(k, '')
                        all_t[m_idx_curr][k] = v_next
                        all_t[m_idx_next][k] = v_curr
                    
                    all_t[m_idx_curr]['uuid'], all_t[m_idx_next]['uuid'] = all_t[m_idx_next]['uuid'], all_t[m_idx_curr]['uuid']
                    
                    self.mark_as_edited(all_t[m_idx_curr]['block_name'])
                    self.refresh_table()
        except Exception as e:
            if DEBUG_MODE:
                with open("bridge_debug.txt", "a") as f: f.write(f"  CRITICAL ERROR move_down: {e}\n")

    def handle_global_paste(self, event=None):
        try:
            text = self.clipboard_get().strip()
        except:
            return

        if not text: return

        # Case 1: Multiple cells are selected (Blue cells)
        if len(self.selected_cells) > 1:
            for row in self.rows:
                u = row.data.get('uuid')
                for k in ['hose', 'conductor']:
                    if (u, k) in self.selected_cells:
                        row.data[k] = text
                        if k in row.widgets and isinstance(row.widgets[k], ctk.CTkEntry):
                            w = row.widgets[k]
                            w.delete(0, tk.END)
                            w.insert(0, text)
                        self.mark_as_edited(row.data['block_name'])
            self.apply_selection_visuals()
            return "break" # Handled!

        # Case 2: Single cell selected or focused with multi-line text
        target_cell = None
        if self.selected_cells:
            target_cell = list(self.selected_cells)[0]
        elif self.last_clicked_cell:
            target_cell = self.last_clicked_cell

        if target_cell:
            u_target, key_target = target_cell
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            
            # If multi-line, spread down from focused cell
            if len(lines) > 1:
                try:
                    all_uuids = [r.data.get('uuid') for r in self.rows]
                    start_idx = all_uuids.index(u_target)
                    for i, line in enumerate(lines):
                        if start_idx + i < len(self.rows):
                            row = self.rows[start_idx + i]
                            row.data[key_target] = line
                            if key_target in row.widgets and isinstance(row.widgets[key_target], ctk.CTkEntry):
                                w = row.widgets[key_target]
                                w.delete(0, tk.END)
                                w.insert(0, line)
                            self.mark_as_edited(row.data['block_name'])
                    return "break"
                except ValueError: pass
            else:
                # Single line, single cell: Let the widget handle it naturally if no multi-selection
                pass

        return None # Let default handler proceed if not specifically intercepted

    def apply_auto_fill(self, target, color):
        # Update the central data in qet_project.terminals
        show_all = "-- ALL --" in self.selected_tbs
        for t in self.qet_project.terminals:
            # Skip if not shown in current view
            if not show_all and t['block_name'] not in self.selected_tbs:
                continue

            current_cond = str(t.get('conductor', '')).strip()
            # Rule: Protect wire numbers. Skip if the field is strictly numeric.
            if target != "RESET" and current_cond.isdigit():
                continue

            cable = str(t.get('cable', '')).upper()
            should_fill = False
            
            if target == "24V" and "24V" in cable:
                should_fill = True
            elif target == "0V" and "0V" in cable:
                should_fill = True
            elif target == "OTHERS" and "24V" not in cable and "0V" not in cable:
                should_fill = True
            elif target == "RESET":
                should_fill = True
            
            if should_fill:
                t['conductor'] = color
                self.mark_as_edited(t['block_name'])
        
        # Sync the Entry widgets BEFORE refresh_table (which calls get_data)
        # to prevent get_data from overwriting the new values with old widget text
        for row in self.rows:
            w = row.widgets.get('conductor')
            if w and isinstance(w, ctk.CTkEntry):
                val = str(row.data.get('conductor', ''))
                if w.get() != val:
                    w.delete(0, tk.END)
                    w.insert(0, val)
        
        # Refresh the UI with the updated central data
        self.refresh_table()

    def apply_auto_bridge(self, level):
        level_str = str(level)
        bridge_key = f"bridge{level}"
        
        # 1. Sync all current inputs to data list
        for row in self.rows:
            row.get_data()
            
        show_all = "-- ALL --" in self.selected_tbs
        target_terminals = [t for t in self.qet_project.terminals 
                           if show_all or t['block_name'] in self.selected_tbs]
        
        # 2. Reset the specific bridge column for the target etage
        for t in target_terminals:
            if str(t.get('etage', '1')).strip() == level_str:
                t[bridge_key] = ""

        # 3. Filter terminals on this level
        level_terminals = [t for t in target_terminals if str(t.get('etage', '1')).strip() == level_str]
        
        if len(level_terminals) < 2:
            self.refresh_table()
            return

        # 4. Chain bridges based on conductor matching
        i = 0
        while i < len(level_terminals) - 1:
            curr = level_terminals[i]
            next_t = level_terminals[i+1]
            
            cond_curr = str(curr.get('cable', '')).strip()
            cond_next = str(next_t.get('cable', '')).strip()
            
            if cond_curr and cond_curr == cond_next:
                # Start or continue a chain
                curr[bridge_key] = "O"
                next_t[bridge_key] = "F"
                self.mark_as_edited(curr['block_name'])
                
                # Scan for longer continuous chain
                j = i + 1
                while j < len(level_terminals) - 1:
                    t_j = level_terminals[j]
                    t_next_j = level_terminals[j+1]
                    val_j = str(t_j.get('cable', '')).strip()
                    val_next_j = str(t_next_j.get('cable', '')).strip()
                    if val_j == val_next_j and val_j != "":
                        t_j[bridge_key] = "O" # Convert previous F to O
                        t_next_j[bridge_key] = "F"
                        j += 1
                    else:
                        break
                i = j + 1
            else:
                i += 1
        
        self.refresh_table()

    def on_create(self):
        try:
            # Purge debug logs at start of generation
            if DEBUG_MODE:
                try:
                    with open("debug_drawing.txt", "w") as f: f.write("")
                    with open("bridge_debug.txt", "w") as f: f.write("")
                except: pass
                with open("bridge_debug.txt", "a") as f:
                    f.write(f"\n--- BATCH CREATION START ---\nTime: {time.ctime()}\n")

            # Final sync for text entries
            for r in self.rows:
                r.get_data()
            
            all_data = self.qet_project.terminals

            # Determine which TBs to create
            tb_names = self.qet_project.tb_names
            choosed = [n for n in tb_names if ("-- ALL --" in self.selected_tbs or n in self.selected_tbs)]

            if not choosed:
                messagebox.showwarning("Warning", "No terminal blocks selected.")
                return

            self.backup_diagram()
            split_val = int(self.settings.get('-CFG_SPLIT-', 30))
            filtered_data = [d for d in all_data if d['block_name'] in choosed]
            
            if not filtered_data:
                messagebox.showwarning("Warning", "The selected terminal blocks contain no data.")
                return

            tb_done = []
            current_tb = []
            memo_tb_name = filtered_data[0]['block_name']
            
            for t in filtered_data:
                if t['block_name'] == memo_tb_name and len(current_tb) < split_val:
                    current_tb.append(t)
                else:
                    self.create_tb_segment(current_tb, tb_done, split_val, filtered_data)
                    current_tb = [t]
                    memo_tb_name = t['block_name']
            
            self.create_tb_segment(current_tb, tb_done, split_val, filtered_data)
            self.qet_project.update_terminals(filtered_data)
            self.qet_project.save_tb(self.qet_file)
            
            messagebox.showinfo("Success", "Terminal blocks created successfully!\nPlease check 'bridge_debug.txt' for consistency.")
            
        except Exception as e:
            import traceback
            err_msg = f"An error occurred during creation:\n{str(e)}\n\n{traceback.format_exc()}"
            with open("error_log.txt", "w") as f:
                f.write(err_msg)
            messagebox.showerror("Creation Error", err_msg)

    def create_tb_segment(self, current_tb, tb_done, split_val, filtered_data):
        name = current_tb[0]['block_name']
        tb_done.append(name)
        slice_num = tb_done.count(name)
        splitted = len([1 for x in filtered_data if x['block_name'] == name]) > split_val
        
        head_text = "{}({})".format(name, slice_num) if splitted else name
        a_block = TerminalBlock(head_text, current_tb, self.settings)
        self.qet_project.insert_tb(head_text, a_block.drawTerminalBlock())

    def backup_diagram(self):
        i = 1
        base = os.path.splitext(self.qet_file)[0]
        while True:
            backup = f"{base}_{i}.qet"
            if not os.path.exists(backup):
                shutil.copyfile(self.qet_file, backup)
                return backup
            i += 1

    def open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("950x750")
        dialog.transient(self)
        dialog.grab_set()

        # Layout Settings (Left) and Image (Right)
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=0)
        main_frame.grid_rowconfigure(0, weight=1)

        scroll_canvas = ctk.CTkScrollableFrame(main_frame)
        scroll_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # --- General ---
        ctk.CTkLabel(scroll_canvas, text="General Settings", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5))
        f_gen = ctk.CTkFrame(scroll_canvas)
        f_gen.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_gen, text="Split every:").pack(side="left", padx=5)
        split_entry = ctk.CTkEntry(f_gen, width=60)
        split_entry.insert(0, self.settings.get('-CFG_SPLIT-', 30))
        split_entry.pack(side="left", padx=5)

        # --- Dimensions (A-J) ---
        ctk.CTkLabel(scroll_canvas, text="Dimensions Settings", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        dim_frame = ctk.CTkFrame(scroll_canvas)
        dim_frame.pack(fill="x", padx=20, pady=5)
        
        entries = {}
        # Grid for A-K
        for i, char in enumerate("ABCDEFGHIJK"):
            row, col = divmod(i, 2)
            lbl = ctk.CTkLabel(dim_frame, text=f"{char}:")
            lbl.grid(row=row, column=col*2, padx=5, pady=5, sticky="e")
            entry = ctk.CTkEntry(dim_frame, width=60)
            entry.insert(0, self.settings.get(f'-CFG_{char}-', ""))
            entry.grid(row=row, column=col*2+1, padx=5, pady=5, sticky="w")
            entries[f'-CFG_{char}-'] = entry

        # --- Fonts ---
        ctk.CTkLabel(scroll_canvas, text="Font Sizes", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        font_frame = ctk.CTkFrame(scroll_canvas)
        font_frame.pack(fill="x", padx=20, pady=5)
        
        fonts = [
            ('-CFG_HEAD_FONT-', "Header"),
            ('-CFG_TERMINAL_FONT-', "Terminal ID"),
            ('-CFG_XREF_FONT-', "Cross Ref"),
            ('-CFG_CONDUCTOR_FONT-', "Conductor")
        ]
        
        font_entries = {}
        for i, (key, label) in enumerate(fonts):
            row, col = divmod(i, 2)
            ctk.CTkLabel(font_frame, text=f"{label}:").grid(row=row, column=col*2, padx=5, pady=5, sticky="e")
            entry = ctk.CTkEntry(font_frame, width=60)
            entry.insert(0, self.settings.get(key, ""))
            entry.grid(row=row, column=col*2+1, padx=5, pady=5, sticky="w")
            font_entries[key] = entry

        def save():
            new_settings = self.settings.copy()
            new_settings['-CFG_SPLIT-'] = split_entry.get()
            for key, entry in entries.items():
                new_settings[key] = entry.get()
            for key, entry in font_entries.items():
                new_settings[key] = entry.get()
            
            # Basic validation
            try:
                for v in new_settings.values():
                    int(v)
                self.settings = new_settings
                self.save_settings_to_file()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "All values must be integers.")

        # Legend Image on the right
        try:
            # Try to find the image in the bundle (PyInstaller) or locally
            img_name = "legend borne.jpg"
            if hasattr(sys, '_MEIPASS'):
                img_path = os.path.join(sys._MEIPASS, img_name)
            else:
                # Local dev paths - looking in assets folder
                img_path = os.path.join(os.path.dirname(__file__), "assets", img_name)
            
            if os.path.exists(img_path):
                pil_img = Image.open(img_path)
                # Scale height to 600, maintain aspect ratio (original 457x820)
                target_h = 600
                target_w = int(457 * (target_h / 820))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(target_w, target_h))
                
                img_label = ctk.CTkLabel(main_frame, image=ctk_img, text="")
                img_label.grid(row=0, column=1, sticky="n", pady=10)
        except Exception as e:
            log.error(f"Could not load settings legend image: {e}")

        ctk.CTkButton(dialog, text="Save Settings", fg_color="green", command=save).pack(pady=20)

    def load_settings(self):
        config_path = os.path.join(os.path.expanduser("~"), CONFIG_FILE)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.settings = json.load(f)
            except:
                self.set_defaults()
        else:
            self.set_defaults()

    def set_defaults(self):
        self.settings = {
            '-CFG_SPLIT-': '30',
            '-CFG_A-': '120', '-CFG_B-': '44', '-CFG_C-': '70', '-CFG_D-': '6', '-CFG_E-': '160',
            '-CFG_F-': '20', '-CFG_G-': '50', '-CFG_H-': '70', '-CFG_I-': '80', '-CFG_J-': '70',
            '-CFG_K-': '20',
            '-CFG_HEAD_FONT-': '13', '-CFG_TERMINAL_FONT-': '9', '-CFG_XREF_FONT-': '6', '-CFG_CONDUCTOR_FONT-': '6'
        }

    def save_settings_to_file(self):
        config_path = os.path.join(os.path.expanduser("~"), CONFIG_FILE)
        with open(config_path, 'w') as f:
            json.dump(self.settings, f)

def get_qet_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Choose a diagram QET file", 
                                           filetypes=[("QET Files", "*.qet"), ("All Files", "*.*")])
    root.destroy()
    return file_path

def main():
    qet_file = get_qet_file()
    if qet_file:
        app = App(qet_file)
        app.mainloop()

if __name__ == "__main__":
    main()
