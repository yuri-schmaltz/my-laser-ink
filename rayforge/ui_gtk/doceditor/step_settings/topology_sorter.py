from typing import Dict, Any, TYPE_CHECKING
from gi.repository import Adw
from ....core.undo import DictItemCommand
from .base import StepComponentSettingsWidget

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor


class TopologySorterSettingsWidget(StepComponentSettingsWidget):
    """UI for configuring the TopologySorter transformer."""

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

        self.enable_row = Adw.SwitchRow(
            title=_("Enable"),
            subtitle=_(
                "Cut inner shapes (holes) before outer shapes (outlines)"
            ),
        )
        self.enable_row.set_active(target_dict.get("enabled", False))
        self.enable_row.connect("notify::active", self._on_enable_toggled)
        self.add(self.enable_row)

    def _on_enable_toggled(self, row, _pspec):
        new_value = row.get_active()
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="enabled",
            new_value=new_value,
            name=_("Toggle Topology Sort"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
        self.history_manager.execute(command)
