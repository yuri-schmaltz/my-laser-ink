from typing import Dict, Any, TYPE_CHECKING
from gi.repository import Gtk, Adw
from ....core.undo import DictItemCommand
from ....pipeline.transformer import ArrayTransformer
from ...shared.adwfix import get_spinrow_int, get_spinrow_float
from ....shared.util.glib import DebounceMixin
from .base import StepComponentSettingsWidget

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor


class ArraySettingsWidget(DebounceMixin, StepComponentSettingsWidget):
    """UI for configuring the ArrayTransformer (step & repeat grid)."""

    def __init__(
        self,
        editor: "DocEditor",
        title: str,
        target_dict: Dict[str, Any],
        page: Adw.PreferencesPage,
        step: "Step",
        **kwargs,
    ):
        transformer = ArrayTransformer.from_dict(target_dict)

        super().__init__(
            editor,
            title,
            description=transformer.description,
            target_dict=target_dict,
            page=page,
            step=step,
            **kwargs,
        )

        rows_adj = Gtk.Adjustment(
            lower=1, upper=100, step_increment=1, page_increment=5
        )
        self.rows_row = Adw.SpinRow(
            title=_("Rows"),
            subtitle=_("Number of copies along the Y axis"),
            adjustment=rows_adj,
        )
        rows_adj.set_value(transformer.rows)
        self.add(self.rows_row)

        cols_adj = Gtk.Adjustment(
            lower=1, upper=100, step_increment=1, page_increment=5
        )
        self.cols_row = Adw.SpinRow(
            title=_("Columns"),
            subtitle=_("Number of copies along the X axis"),
            adjustment=cols_adj,
        )
        cols_adj.set_value(transformer.cols)
        self.add(self.cols_row)

        x_adj = Gtk.Adjustment(
            lower=0.1, upper=1000.0, step_increment=1.0, page_increment=10.0
        )
        self.x_row = Adw.SpinRow(
            title=_("X Spacing (mm)"),
            subtitle=_("Horizontal distance between copies"),
            adjustment=x_adj,
            digits=2,
        )
        x_adj.set_value(transformer.x_spacing_mm)
        self.add(self.x_row)

        y_adj = Gtk.Adjustment(
            lower=0.1, upper=1000.0, step_increment=1.0, page_increment=10.0
        )
        self.y_row = Adw.SpinRow(
            title=_("Y Spacing (mm)"),
            subtitle=_("Vertical distance between copies"),
            adjustment=y_adj,
            digits=2,
        )
        y_adj.set_value(transformer.y_spacing_mm)
        self.add(self.y_row)

        self.rows_row.connect(
            "changed",
            lambda r: self._debounce(self._on_rows_changed, r),
        )
        self.cols_row.connect(
            "changed",
            lambda r: self._debounce(self._on_cols_changed, r),
        )
        self.x_row.connect(
            "changed",
            lambda r: self._debounce(self._on_x_spacing_changed, r),
        )
        self.y_row.connect(
            "changed",
            lambda r: self._debounce(self._on_y_spacing_changed, r),
        )

    def _on_rows_changed(self, spin_row):
        new_value = get_spinrow_int(spin_row)
        if new_value == self.target_dict.get("rows"):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="rows",
            new_value=new_value,
            name=_("Change array rows"),
            on_change_callback=self.step.per_step_transformer_changed.send,
        )
        self.history_manager.execute(command)

    def _on_cols_changed(self, spin_row):
        new_value = get_spinrow_int(spin_row)
        if new_value == self.target_dict.get("cols"):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="cols",
            new_value=new_value,
            name=_("Change array columns"),
            on_change_callback=self.step.per_step_transformer_changed.send,
        )
        self.history_manager.execute(command)

    def _on_x_spacing_changed(self, spin_row):
        new_value = get_spinrow_float(spin_row)
        if new_value == self.target_dict.get("x_spacing_mm"):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="x_spacing_mm",
            new_value=new_value,
            name=_("Change array X spacing"),
            on_change_callback=self.step.per_step_transformer_changed.send,
        )
        self.history_manager.execute(command)

    def _on_y_spacing_changed(self, spin_row):
        new_value = get_spinrow_float(spin_row)
        if new_value == self.target_dict.get("y_spacing_mm"):
            return
        command = DictItemCommand(
            target_dict=self.target_dict,
            key="y_spacing_mm",
            new_value=new_value,
            name=_("Change array Y spacing"),
            on_change_callback=self.step.per_step_transformer_changed.send,
        )
        self.history_manager.execute(command)
