from typing import Dict, Any, TYPE_CHECKING
from gi.repository import Gtk, Adw
from ....core.undo import DictItemCommand
from .base import StepComponentSettingsWidget

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor

_MODES = ["threshold", "dither", "grayscale"]


class AdvancedRasterizerSettingsWidget(StepComponentSettingsWidget):
    """UI for configuring the AdvancedRasterizer producer."""

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

        params = self.target_dict.setdefault("params", {})
        current_mode = params.get("mode", "threshold")

        mode_labels = [
            _("Threshold (B&W)"),
            _("Dither (Floyd-Steinberg)"),
            _("Grayscale (S-Power)"),
        ]
        mode_model = Gtk.StringList.new(mode_labels)
        selected = (
            _MODES.index(current_mode) if current_mode in _MODES else 0
        )
        self.mode_row = Adw.ComboRow(
            title=_("Mode"),
            subtitle=_(
                "Threshold: binary on/off.  "
                "Dither: Floyd-Steinberg halftone.  "
                "Grayscale: variable S-power per pixel."
            ),
            model=mode_model,
        )
        self.mode_row.set_selected(selected)
        self.mode_row.connect("notify::selected", self._on_mode_changed)
        self.add(self.mode_row)

        threshold_adj = Gtk.Adjustment(
            lower=0,
            upper=255,
            step_increment=1,
            page_increment=10,
            value=params.get("threshold", 128),
        )
        self.threshold_row = Adw.SpinRow(
            title=_("Threshold"),
            subtitle=_("Pixel brightness cutoff for Threshold mode (0-255)"),
            adjustment=threshold_adj,
        )
        self.threshold_row.connect("changed", self._on_threshold_changed)
        self.threshold_row.set_sensitive(current_mode == "threshold")
        self.add(self.threshold_row)

    def _on_mode_changed(self, combo_row, _pspec):
        idx = combo_row.get_selected()
        mode = _MODES[idx] if 0 <= idx < len(_MODES) else "threshold"
        self.threshold_row.set_sensitive(mode == "threshold")
        params = self.target_dict.setdefault("params", {})
        command = DictItemCommand(
            target_dict=params,
            key="mode",
            new_value=mode,
            name=_("Change Rasterizer Mode"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)

    def _on_threshold_changed(self, spin_row):
        new_value = int(spin_row.get_value())
        params = self.target_dict.setdefault("params", {})
        command = DictItemCommand(
            target_dict=params,
            key="threshold",
            new_value=new_value,
            name=_("Change Threshold"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)
