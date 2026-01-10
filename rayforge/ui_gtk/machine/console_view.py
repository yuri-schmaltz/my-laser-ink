import logging
import asyncio
from gi.repository import Gtk, Adw, Pango, GLib, Gdk
from ...context import get_context
from ...machine.models.machine import Machine

logger = logging.getLogger(__name__)

class ConsoleView(Gtk.Box):
    """
    A simple terminal-like console for sending raw commands to the machine
    and viewing incoming responses.
    """

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, **kwargs)
        
        # --- Output Area ---
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.add_css_class("view")
        
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_monospace(True)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        
        # Use a dark terminal style if possible
        self.text_view.add_css_class("console-text")
        
        self.scrolled_window.set_child(self.text_view)
        self.append(self.scrolled_window)
        
        # --- Input Area ---
        self.input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.input_box.set_margin_start(6)
        self.input_box.set_margin_end(6)
        self.input_box.set_margin_bottom(6)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(_("Enter command..."))
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._on_entry_activate)
        
        self.send_button = Gtk.Button(label=_("Send"))
        self.send_button.connect("clicked", self._on_entry_activate)
        
        self.clear_button = Gtk.Button(icon_name="edit-clear-all-symbolic")
        self.clear_button.set_tooltip_text(_("Clear Console"))
        self.clear_button.connect("clicked", self._on_clear_clicked)
        
        self.input_box.append(self.entry)
        self.input_box.append(self.send_button)
        self.input_box.append(self.clear_button)
        self.append(self.input_box)
        
        # --- Connection to Machine ---
        self._current_machine: Optional[Machine] = None
        context = get_context()
        context.config.changed.connect(self._on_config_changed)
        
        # Initial machine
        self._set_machine(context.config.machine)

    def _on_config_changed(self, sender, **kwargs):
        self._set_machine(get_context().config.machine)

    def _set_machine(self, machine: Optional[Machine]):
        if self._current_machine:
            self._current_machine.received.disconnect(self._on_data_received)
        
        self._current_machine = machine
        if self._current_machine:
            self._current_machine.received.connect(self._on_data_received)
            self._append_log(f"--- Switched to {machine.name} ---", "info")

    def _on_data_received(self, sender, data: bytes):
        try:
            text = data.decode("utf-8", errors="replace")
            # Usually machine data comes in lines
            GLib.idle_add(self._append_log, text, "received")
        except Exception as e:
            logger.error(f"Console: Error decoding data: {e}")

    def _on_entry_activate(self, _widget):
        text = self.entry.get_text().strip()
        if not text:
            return
        
        if self._current_machine:
            self._append_log(f"> {text}", "sent")
            # Note: run_raw is usually async, but here we just trigger it
            asyncio.create_task(self._current_machine.driver.run_raw(text))
            self.entry.set_text("")
        else:
            self._append_log(_("Error: No machine connected."), "error")

    def _on_clear_clicked(self, _button):
        buffer = self.text_view.get_buffer()
        buffer.set_text("")

    def _append_log(self, text: str, category: str):
        buffer = self.text_view.get_buffer()
        end_iter = buffer.get_end_iter()
        
        # We could use tags for coloring, but let's keep it simple for now
        buffer.insert(end_iter, text + "\n")
        
        # Scroll to bottom
        adj = self.scrolled_window.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False # For GLib.idle_add
