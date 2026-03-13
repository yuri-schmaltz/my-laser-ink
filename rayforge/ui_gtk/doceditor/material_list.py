"""Material list UI components for Rayforge."""

import uuid
import logging
from typing import Optional, cast
from gi.repository import Gtk, Adw
from blinker import Signal
from ...context import get_context
from ...core.material import Material, MaterialAppearance
from ...core.material_library import MaterialLibrary
from ..icons import get_icon
from ..shared.preferences_group import PreferencesGroupWithButton
from .add_material_dialog import AddMaterialDialog

logger = logging.getLogger(__name__)


class MaterialRow(Gtk.Box):
    """A widget representing a single Material in a ListBox."""

    def __init__(
        self,
        material: Material,
        library: MaterialLibrary,
        on_delete_callback,
        on_edit_callback,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.material = material
        self.library = library
        self.on_delete_callback = on_delete_callback
        self.on_edit_callback = on_edit_callback
        self._setup_ui()

    def _setup_ui(self):
        """Builds the user interface for the row."""
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(12)
        self.set_margin_end(6)

        color_box = Gtk.Box()
        color_box.set_size_request(24, 24)
        color_box.set_valign(Gtk.Align.CENTER)
        color_box.add_css_class("material-color")
        color_provider = Gtk.CssProvider()
        color_data = (
            ".material-color { "
            "  border-radius: 50%; "
            "  border: 1px solid rgba(0,0,0,0.1); "
            "  background-color: %s; "
            "}"
        ) % self.material.get_display_color()
        color_provider.load_from_string(color_data)
        color_box.get_style_context().add_provider(
            color_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.prepend(color_box)

        # Tooltip for easy preview of parameters
        tooltip = _(
            "Thickness: {thickness}mm\n"
            "Speed: {speed}mm/min\n"
            "Power: {power}%"
        ).format(
            thickness=self.material.thickness,
            speed=self.material.speed,
            power=self.material.power,
        )
        self.set_tooltip_text(tooltip)

        labels_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True
        )
        self.append(labels_box)

        title_label = Gtk.Label(
            label=self.material.name,
            halign=Gtk.Align.START,
            xalign=0,
        )
        labels_box.append(title_label)

        subtitle_label = Gtk.Label(
            label=self.material.category,
            halign=Gtk.Align.START,
            xalign=0,
        )
        subtitle_label.add_css_class("dim-label")
        labels_box.append(subtitle_label)

        if not self.library.read_only:
            # Suffix area for buttons
            suffix_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
            self.append(suffix_box)

            edit_button = Gtk.Button(child=get_icon("document-edit-symbolic"))
            edit_button.add_css_class("flat")
            edit_button.connect("clicked", self._on_edit_clicked)
            suffix_box.append(edit_button)

            delete_button = Gtk.Button(child=get_icon("delete-symbolic"))
            delete_button.add_css_class("flat")
            delete_button.connect("clicked", self._on_delete_clicked)
            suffix_box.append(delete_button)

    def _on_delete_clicked(self, button: Gtk.Button):
        """Handle the delete button being clicked."""
        self.on_delete_callback(self.material)

    def _on_edit_clicked(self, button: Gtk.Button):
        """Handle the edit button being clicked."""
        self.on_edit_callback(self.material)


class MaterialListWidget(PreferencesGroupWithButton):
    """
    An Adwaita widget for displaying materials from a selected library.
    """

    def __init__(self, **kwargs):
        # This list correctly uses the default SelectionMode.NONE
        super().__init__(button_label=_("Add New Material"), **kwargs)
        self.material_added = Signal()
        self.material_deleted = Signal()
        self._filter_text = ""
        self._setup_ui()
        self._current_library: Optional[MaterialLibrary] = None

    def _setup_ui(self):
        """Configures the widget's list box and placeholder."""
        container = self.get_first_child()
        if isinstance(container, Gtk.Box):
            self.search_entry = Gtk.SearchEntry(
                placeholder_text=_("Search materials..."),
                margin_start=12,
                margin_end=12,
                margin_top=8,
                margin_bottom=0,
            )
            container.prepend(self.search_entry)
            self.search_entry.connect("search-changed", self._on_search_changed)

        placeholder = Gtk.Label(
            label=_("No materials found."),
            halign=Gtk.Align.CENTER,
            margin_top=12,
            margin_bottom=12,
        )
        placeholder.add_css_class("dim-label")
        self.list_box.set_placeholder(placeholder)
        self.list_box.set_show_separators(True)
        self.list_box.connect("row-activated", self._on_row_activated)

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        """Update filter text and refresh list."""
        self._filter_text = entry.get_text().lower().strip()
        self._populate_materials()

    def _on_row_activated(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        """Handle double-click (or Enter) to edit material."""
        child = row.get_child()
        if isinstance(child, MaterialRow):
            self._on_edit_material(child.material)

    def set_library(self, library: Optional[MaterialLibrary]):
        """Set the current library and update the materials list."""
        logger.debug(
            f"MaterialListEditor: Setting library to "
            f"'{library.library_id if library is not None else 'None'}'"
        )
        self._current_library = library
        self.add_button.set_sensitive(
            library is not None and not library.read_only
        )
        self._populate_materials()

    def _populate_materials(self):
        """Populate the list with materials from the current library."""
        if self._current_library is None:
            self.set_items([])
            return

        materials = sorted(
            self._current_library.get_all_materials(), key=lambda m: m.name
        )

        if self._filter_text:
            materials = [
                m
                for m in materials
                if self._filter_text in m.name.lower()
                or self._filter_text in m.category.lower()
            ]

        self.set_items(materials)

    def create_row_widget(self, item: Material) -> Gtk.Widget:
        """Creates a MaterialRow for the given material."""
        assert self._current_library is not None
        return MaterialRow(
            item,
            self._current_library,
            self._on_delete_material,
            self._on_edit_material,
        )

    def _on_delete_material(self, material: Material):
        """Handle material deletion with confirmation."""
        if self._current_library is None:
            return

        # Reject deletion if the material is still in use
        root = self.get_root()
        recipe_mgr = get_context().recipe_mgr
        if recipe_mgr.is_material_in_use(material.uid):
            err_dialog = Adw.MessageDialog(
                transient_for=cast(Gtk.Window, root) if root else None,
                heading=_("Cannot Delete Material"),
                body=_(
                    "This material is currently used by one or more recipes. "
                    "Please remove the recipes that use this material before "
                    "deleting it."
                ),
            )
            err_dialog.add_response("ok", _("OK"))
            err_dialog.present()
            return  # Stop the deletion process

        # Ask for confirmation
        dialog = Adw.MessageDialog(
            transient_for=cast(Gtk.Window, root) if root else None,
            heading=_("Delete '{name}'?").format(name=material.name),
            body=_(
                "The material will be permanently removed from the library. "
                "This action cannot be undone."
            ),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_default_response("cancel")

        def on_response(d, response_id):
            if response_id == "delete":
                if self._current_library is not None:
                    if self._current_library.remove_material(material.uid):
                        self._populate_materials()
                        self.material_deleted.send(
                            self, library=self._current_library
                        )
                    else:
                        logger.error(
                            f"Failed to remove material '{material.uid}'"
                        )
            d.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def _on_edit_material(self, material: Material):
        """Handle material editing."""
        if self._current_library is None:
            return

        root = self.get_root()
        dialog = AddMaterialDialog(
            material=material,
            transient_for=cast(Gtk.Window, root) if root else None,
        )

        def on_response(d, response_id):
            if response_id in ("add", "save"):
                data = d.get_material_data()
                if data["name"] and self._current_library is not None:
                    self._update_material(
                        data, material, self._current_library
                    )
            d.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def _update_material(
        self, data: dict, material: Material, library: MaterialLibrary
    ):
        """Update an existing material in the library."""
        # Update material properties
        material.name = data["name"]
        material.category = data["category"]
        material.appearance.color = data["color"]
        material.thickness = data["thickness"]
        material.speed = data["speed"]
        material.power = data["power"]

        # Save the updated material
        if material.file_path:
            try:
                material.save_to_file(material.file_path)
                self._populate_materials()
                logger.info(
                    f"Updated material '{data['name']}' in library "
                    f"'{library.library_id}'"
                )
                
                # Sync to SettingsManager
                get_context().material_mgr.sync_library_to_settings(library)

                self.material_added.send(self, library=library)
            except Exception as e:
                logger.error(f"Failed to update material: {e}")
                root = self.get_root()
                err_dialog = Adw.MessageDialog(
                    transient_for=cast(Gtk.Window, root) if root else None,
                    heading=_("Error"),
                    body=_("Failed to update material."),
                )
                err_dialog.add_response("ok", _("OK"))
                err_dialog.present()

    def _on_add_clicked(self, button: Gtk.Button):
        """Handle add material button click."""
        logger.debug("MaterialListEditor: Add material button clicked")
        if self._current_library is None:
            logger.error(
                "MaterialListEditor: _on_add_clicked failed because "
                "_current_library is None. The dialog will not be shown."
            )
            return

        root = self.get_root()
        dialog = AddMaterialDialog(
            transient_for=cast(Gtk.Window, root) if root else None
        )

        def on_response(d, response_id):
            if response_id == "add":
                data = d.get_material_data()
                if data["name"] and self._current_library is not None:
                    self._add_material(data, self._current_library)
            d.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def _add_material(self, data: dict, library: MaterialLibrary):
        """Add a new material to the current library."""
        material = Material(
            uid=str(uuid.uuid4()),
            name=data["name"],
            description="",
            category=data["category"],
            appearance=MaterialAppearance(color=data["color"]),
            thickness=data["thickness"],
            speed=data["speed"],
            power=data["power"],
        )

        if library.add_material(material):
            self._populate_materials()
            logger.info(
                f"Added material '{data['name']}' to library "
                f"'{library.library_id}'"
            )

            # Sync to SettingsManager
            get_context().material_mgr.sync_library_to_settings(library)

            self.material_added.send(self, library=library)
        else:
            root = self.get_root()
            err_dialog = Adw.MessageDialog(
                transient_for=cast(Gtk.Window, root) if root else None,
                heading=_("Error"),
                body=_("Failed to add material to library."),
            )
            err_dialog.add_response("ok", _("OK"))
            err_dialog.present()
