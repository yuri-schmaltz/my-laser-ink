from typing import Dict, Any, TYPE_CHECKING
from gi.repository import Gtk, Adw
from ....core.undo import DictItemCommand
from ....shared.util.glib import DebounceMixin
from ...shared.adwfix import get_spinrow_float
from .base import StepComponentSettingsWidget

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor


class LeadInOutSettingsWidget(DebounceMixin, StepComponentSettingsWidget):
    """UI for configuring the LeadInOutTransformer."""

    def __init__(
        self,
        editor: "DocEditor",
        title: str,
        target_dict: Dict[str, Any],
        page: Adw.PreferencesPage,
        step: "Step",
        **kwargs,
    ):
        super().__init__(
            editor,
            title,
            target_dict=target_dict,
            page=page,
            step=step,
            **kwargs,
        )

        enabled = target_dict.get("enabled", False)

        self.enable_row = Adw.SwitchRow(
            title=_("Enable"),
            subtitle=_(
                "Add entry approach and exit moves to each cutting path"
            ),
        )
        self.enable_row.set_active(enabled)
        self.enable_row.connect("notify::active", self._on_enable_toggled)
        self.add(self.enable_row)

        lead_in_adj = Gtk.Adjustment(
            lower=0.0,
            upper=20.0,
            step_increment=0.1,
            page_increment=1.0,
            value=target_dict.get("lead_in_mm", 1.0),
        )
        self.lead_in_row = Adw.SpinRow(
            title=_("Lead-In Distance"),
            subtitle=_("Approach distance before the cut entry (mm)"),
            adjustment=lead_in_adj,
            digits=1,
        )
        self.lead_in_row.set_sensitive(enabled)
        self.lead_in_row.connect(
            "changed",
            lambda r: self._debounce(
                self._on_value_changed, "lead_in_mm", r
            ),
        )
        self.add(self.lead_in_row)

        lead_out_adj = Gtk.Adjustment(
            lower=0.0,
            upper=20.0,
            step_increment=0.1,
            page_increment=1.0,
            value=target_dict.get("lead_out_mm", 0.5),
        )
        self.lead_out_row = Adw.SpinRow(
            title=_("Lead-Out Distance"),
            subtitle=_("Exit extension after the last cut move (mm)"),
            adjustment=lead_out_adj,
            digits=1,
        )
        self.lead_out_row.set_sensitive(enabled)
        self.lead_out_row.connect(
            "changed",
            lambda r: self._debounce(
                self._on_value_changed, "lead_out_mm", r
            ),
        )
        self.add(self.lead_out_row)

        self.enable_row.connect(
            "notify::active",
            self._on_sensitivity_toggled,
            self.lead_in_row,
            self.lead_out_row,
        )

    def _on_enable_toggled(self, row, _pspec):
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="enabled",
            new_value=row.get_active(),
            name=_("Toggle Lead-In/Lead-Out"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)

    def _on_sensitivity_toggled(self, row, _pspec, *widgets):
        is_active = row.get_active()
        for w in widgets:
            w.set_sensitive(is_active)

    def _on_value_changed(self, key: str, spin_row):
        new_value = round(get_spinrow_float(spin_row), 1)
        if new_value == self.target_dict.get(key):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key=key,
            new_value=new_value,
            name=_("Change Lead Distance"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)
