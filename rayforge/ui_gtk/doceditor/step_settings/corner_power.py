from typing import Dict, Any, TYPE_CHECKING
from gi.repository import Gtk, Adw
from ....core.undo import DictItemCommand
from ....shared.util.glib import DebounceMixin
from ...shared.adwfix import get_spinrow_float
from .base import StepComponentSettingsWidget

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor


class CornerPowerSettingsWidget(DebounceMixin, StepComponentSettingsWidget):
    """UI for configuring the CornerPowerTransformer."""

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
                "Reduce laser power at sharp corners to avoid over-burning"
            ),
        )
        self.enable_row.set_active(enabled)
        self.enable_row.connect("notify::active", self._on_enable_toggled)
        self.add(self.enable_row)

        min_angle_adj = Gtk.Adjustment(
            lower=0.0,
            upper=179.0,
            step_increment=1.0,
            page_increment=10.0,
            value=target_dict.get("min_angle_deg", 30.0),
        )
        self.min_angle_row = Adw.SpinRow(
            title=_("Threshold Angle"),
            subtitle=_(
                "Corners sharper than this angle trigger power reduction (°)"
            ),
            adjustment=min_angle_adj,
            digits=0,
        )
        self.min_angle_row.set_sensitive(enabled)
        self.min_angle_row.connect(
            "changed",
            lambda r: self._debounce(
                self._on_value_changed, "min_angle_deg", r
            ),
        )
        self.add(self.min_angle_row)

        full_angle_adj = Gtk.Adjustment(
            lower=0.0,
            upper=180.0,
            step_increment=1.0,
            page_increment=10.0,
            value=target_dict.get("full_angle_deg", 90.0),
        )
        self.full_angle_row = Adw.SpinRow(
            title=_("Full Reduction Angle"),
            subtitle=_(
                "Corners at or beyond this angle get maximum"
                " power reduction (°)"
            ),
            adjustment=full_angle_adj,
            digits=0,
        )
        self.full_angle_row.set_sensitive(enabled)
        self.full_angle_row.connect(
            "changed",
            lambda r: self._debounce(
                self._on_value_changed, "full_angle_deg", r
            ),
        )
        self.add(self.full_angle_row)

        min_power_adj = Gtk.Adjustment(
            lower=0.0,
            upper=1.0,
            step_increment=0.05,
            page_increment=0.1,
            value=target_dict.get("min_power_factor", 0.4),
        )
        self.min_power_row = Adw.SpinRow(
            title=_("Minimum Power Factor"),
            subtitle=_(
                "Power multiplier at the sharpest corners (0.0-1.0)"
            ),
            adjustment=min_power_adj,
            digits=2,
        )
        self.min_power_row.set_sensitive(enabled)
        self.min_power_row.connect(
            "changed",
            lambda r: self._debounce(
                self._on_value_changed, "min_power_factor", r
            ),
        )
        self.add(self.min_power_row)

        self.enable_row.connect(
            "notify::active",
            self._on_sensitivity_toggled,
            self.min_angle_row,
            self.full_angle_row,
            self.min_power_row,
        )

    def _on_enable_toggled(self, row, _pspec):
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="enabled",
            new_value=row.get_active(),
            name=_("Toggle Corner Power Drop"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)

    def _on_sensitivity_toggled(self, row, _pspec, *widgets):
        is_active = row.get_active()
        for w in widgets:
            w.set_sensitive(is_active)

    def _on_value_changed(self, key: str, spin_row):
        new_value = round(get_spinrow_float(spin_row), 2)
        if new_value == self.target_dict.get(key):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key=key,
            new_value=new_value,
            name=_("Change Corner Power Setting"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)
