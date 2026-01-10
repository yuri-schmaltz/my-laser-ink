import logging
from typing import List, Optional, Dict, cast
from gi.repository import Gtk, Adw, Gio, Gdk, GLib, Pango

from ...machine.models.machine import Machine
from ...machine.models.macro import Macro, MacroTrigger

logger = logging.getLogger(__name__)

class MacroEditorDialog(Adw.Window):
    """
    A dialog for managing machine macros and hooks.
    """
    def __init__(self, machine: Machine, transient_for: Gtk.Window):
        super().__init__(
            title=_("Macro Editor"),
            transient_for=transient_for,
            modal=True,
            default_width=800,
            default_height=600,
        )
        self.machine = machine

        # Main Layout
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_content(content)

        # Left Sidebar: Macro List
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=250)
        sidebar.add_css_class("background")
        content.append(sidebar)

        list_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        list_toolbar.set_margin_all(6)
        sidebar.append(list_toolbar)

        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.connect("clicked", self._on_add_macro_clicked)
        list_toolbar.append(add_btn)

        self.list_box = Gtk.ListBox()
        self.list_box.set_vexpand(True)
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self._on_row_selected)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.list_box)
        sidebar.append(scrolled)

        # Right Area: Editor
        self.editor_stack = Gtk.Stack()
        self.editor_stack.set_hexpand(True)
        content.append(self.editor_stack)

        empty_box = Gtk.CenterBox()
        empty_box.set_center_widget(Gtk.Label(label=_("Select or create a macro to edit")))
        self.editor_stack.add_named(empty_box, "empty")

        edit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        edit_box.set_margin_all(18)
        self.editor_stack.add_named(edit_box, "editor")

        # Name field
        name_group = Adw.PreferencesGroup()
        edit_box.append(name_group)
        self.name_row = Adw.EntryRow(title=_("Name"))
        self.name_row.connect("changed", self._on_field_changed)
        name_group.add(self.name_row)

        # Trigger selection
        trigger_group = Adw.PreferencesGroup(title=_("Automation"))
        edit_box.append(trigger_group)
        self.trigger_row = Adw.ComboRow(title=_("Run on event"))
        
        # Populate triggers
        self.trigger_model = Gtk.StringList()
        self.trigger_model.append(_("None"))
        for trigger in MacroTrigger:
            self.trigger_model.append(trigger.value)
        self.trigger_row.set_model(self.trigger_model)
        self.trigger_row.connect("notify::selected", self._on_field_changed)
        trigger_group.add(self.trigger_row)

        # G-code Editor (TextView)
        code_group = Adw.PreferencesGroup(title=_("G-code"))
        edit_box.append(code_group)
        
        scrolled_code = Gtk.ScrolledWindow()
        scrolled_code.set_min_content_height(300)
        scrolled_code.set_vexpand(True)
        self.code_view = Gtk.TextView()
        self.code_view.set_monospace(True)
        self.code_view.get_buffer().connect("changed", self._on_field_changed)
        scrolled_code.set_child(self.code_view)
        code_group.add(scrolled_code)

        # Footer Actions
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        edit_box.append(footer)

        self.delete_btn = Gtk.Button(label=_("Delete Macro"))
        self.delete_btn.add_css_class("destructive-action")
        self.delete_btn.connect("clicked", self._on_delete_clicked)
        footer.append(self.delete_btn)

        self.save_btn = Gtk.Button(label=_("Save"))
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self._on_save_clicked)
        footer.append(self.save_btn)

        self._active_macro: Optional[Macro] = None
        self._refresh_list()
        self.editor_stack.set_visible_child_name("empty")

    def _refresh_list(self):
        # Clear
        while row := self.list_box.get_first_child():
            self.list_box.remove(row)
        
        # Populate
        for macro_uid, macro in self.machine.macros.items():
            row = Adw.ActionRow(title=macro.name)
            row.set_metadata("uid", macro_uid)
            self.list_box.append(row)

    def _on_row_selected(self, listbox, row):
        if not row:
            self._active_macro = None
            self.editor_stack.set_visible_child_name("empty")
            return
        
        uid = row.get_metadata("uid")
        self._active_macro = self.machine.macros[uid]
        self._load_macro_to_ui(self._active_macro)
        self.editor_stack.set_visible_child_name("editor")

    def _load_macro_to_ui(self, macro: Macro):
        self._loading = True
        self.name_row.set_text(macro.name)
        buffer = self.code_view.get_buffer()
        buffer.set_text("\n".join(macro.code))
        
        # Find if this macro is assigned to any trigger
        selected_idx = 0
        for i, trigger in enumerate(MacroTrigger):
            if self.machine.hookmacros.get(trigger) == macro:
                selected_idx = i + 1
                break
        self.trigger_row.set_selected(selected_idx)
        self._loading = False

    def _on_add_macro_clicked(self, btn):
        new_macro = Macro(name=_("New Macro"))
        self.machine.add_macro(new_macro)
        self._refresh_list()
        # Select the new macro
        for i in range(100): # safety break
            row = self.list_box.get_row_at_index(i)
            if not row: break
            if row.get_metadata("uid") == new_macro.uid:
                self.list_box.select_row(row)
                break

    def _on_field_changed(self, *args):
        pass # We use explicit Save button

    def _on_save_clicked(self, btn):
        if not self._active_macro:
            return
        
        self._active_macro.name = self.name_row.get_text()
        buffer = self.code_view.get_buffer()
        start, end = buffer.get_bounds()
        self._active_macro.code = buffer.get_text(start, end, True).splitlines()
        
        # Handle trigger assignment
        # First clear old assignments for THIS macro
        triggers_to_clear = [t for t, m in self.machine.hookmacros.items() if m == self._active_macro]
        for t in triggers_to_clear:
            del self.machine.hookmacros[t]
        
        # Assign new trigger
        idx = self.trigger_row.get_selected()
        if idx > 0:
            trigger = list(MacroTrigger)[idx - 1]
            self.machine.hookmacros[trigger] = self._active_macro
        
        self._refresh_list()
        # Reselect
        for i in range(100):
            row = self.list_box.get_row_at_index(i)
            if not row: break
            if row.get_metadata("uid") == self._active_macro.uid:
                self.list_box.select_row(row)
                break
        
        self.machine.changed.send(self.machine)

    def _on_delete_clicked(self, btn):
        if not self._active_macro:
            return
        
        self.machine.remove_macro(self._active_macro.uid)
        self._active_macro = None
        self._refresh_list()
        self.editor_stack.set_visible_child_name("empty")
