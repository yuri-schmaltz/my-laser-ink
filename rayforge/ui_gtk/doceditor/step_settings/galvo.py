from typing import Dict, Any, TYPE_CHECKING, cast
from gi.repository import Gtk, Adw
from .base import StepComponentSettingsWidget
from ....pipeline.producer.base import OpsProducer
from ....pipeline.producer.galvo import GalvoProducer
from ...shared.adwfix import get_spinrow_float, get_spinrow_int
from ....shared.util.glib import DebounceMixin

if TYPE_CHECKING:
    from ....core.step import Step
    from ....doceditor.editor import DocEditor


class GalvoProducerSettingsWidget(
    DebounceMixin, StepComponentSettingsWidget
):
    """UI for configuring the GalvoProducer for high-speed laser marking."""

    def __init__(
        self,
        editor: "DocEditor",
        title: str,
        target_dict: Dict[str, Any],
        page: Adw.PreferencesPage,
        step: "Step",
        **kwargs,
    ):
        producer = cast(GalvoProducer, OpsProducer.from_dict(target_dict))

        super().__init__(
            editor,
            title,
            target_dict=target_dict,
            page=page,
            step=step,
            **kwargs,
        )

        # Speeds Group
        speeds_group = Adw.PreferencesGroup(title=_("Speeds"))
        self.add(speeds_group)

        # Marking Speed
        marking_speed_adj = Gtk.Adjustment(lower=1, upper=10000, step_increment=10, page_increment=100)
        self.marking_speed_row = Adw.SpinRow(
            title=_("Marking Speed (mm/s)"),
            adjustment=marking_speed_adj,
            digits=0,
        )
        marking_speed_adj.set_value(producer.marking_speed)
        speeds_group.add(self.marking_speed_row)

        # Travel Speed
        travel_speed_adj = Gtk.Adjustment(lower=1, upper=20000, step_increment=100, page_increment=1000)
        self.travel_speed_row = Adw.SpinRow(
            title=_("Travel Speed (mm/s)"),
            adjustment=travel_speed_adj,
            digits=0,
        )
        travel_speed_adj.set_value(producer.travel_speed)
        speeds_group.add(self.travel_speed_row)

        # Delays Group (Microseconds)
        delays_group = Adw.PreferencesGroup(title=_("Delays (μs)"))
        self.add(delays_group)

        # Laser On Delay
        on_delay_adj = Gtk.Adjustment(lower=0, upper=10000, step_increment=10, page_increment=100)
        self.on_delay_row = Adw.SpinRow(title=_("Laser On Delay"), adjustment=on_delay_adj)
        on_delay_adj.set_value(producer.laser_on_delay)
        delays_group.add(self.on_delay_row)

        # Laser Off Delay
        off_delay_adj = Gtk.Adjustment(lower=0, upper=10000, step_increment=10, page_increment=100)
        self.off_delay_row = Adw.SpinRow(title=_("Laser Off Delay"), adjustment=off_delay_adj)
        off_delay_adj.set_value(producer.laser_off_delay)
        delays_group.add(self.off_delay_row)

        # Poly Delay
        poly_delay_adj = Gtk.Adjustment(lower=0, upper=5000, step_increment=10, page_increment=100)
        self.poly_delay_row = Adw.SpinRow(title=_("Poly Delay"), adjustment=poly_delay_adj)
        poly_delay_adj.set_value(producer.poly_delay)
        delays_group.add(self.poly_delay_row)

        # End Delay
        end_delay_adj = Gtk.Adjustment(lower=0, upper=10000, step_increment=100, page_increment=1000)
        self.end_delay_row = Adw.SpinRow(title=_("End Delay"), adjustment=end_delay_adj)
        end_delay_adj.set_value(producer.end_delay)
        delays_group.add(self.end_delay_row)

        # Laser Parameters Group
        laser_group = Adw.PreferencesGroup(title=_("Laser Parameters"))
        self.add(laser_group)

        # Frequency
        freq_adj = Gtk.Adjustment(lower=1, upper=1000, step_increment=1, page_increment=10)
        self.freq_row = Adw.SpinRow(title=_("Frequency (kHz)"), adjustment=freq_adj)
        freq_adj.set_value(producer.frequency)
        laser_group.add(self.freq_row)

        # Power
        power_adj = Gtk.Adjustment(lower=0, upper=100, step_increment=1, page_increment=10)
        self.power_row = Adw.SpinRow(title=_("Power (%)"), adjustment=power_adj, digits=1)
        power_adj.set_value(producer.power)
        laser_group.add(self.power_row)

        # Connect signals
        self.marking_speed_row.connect("changed", lambda r: self._debounce_param("marking_speed", get_spinrow_float(r)))
        self.travel_speed_row.connect("changed", lambda r: self._debounce_param("travel_speed", get_spinrow_float(r)))
        self.on_delay_row.connect("changed", lambda r: self._debounce_param("laser_on_delay", get_spinrow_int(r)))
        self.off_delay_row.connect("changed", lambda r: self._debounce_param("laser_off_delay", get_spinrow_int(r)))
        self.poly_delay_row.connect("changed", lambda r: self._debounce_param("poly_delay", get_spinrow_int(r)))
        self.end_delay_row.connect("changed", lambda r: self._debounce_param("end_delay", get_spinrow_int(r)))
        self.freq_row.connect("changed", lambda r: self._debounce_param("frequency", get_spinrow_int(r)))
        self.power_row.connect("changed", lambda r: self._debounce_param("power", get_spinrow_float(r)))

    def _debounce_param(self, key: str, value: Any):
        self._debounce(self._on_param_changed, key, value)

    def _on_param_changed(self, key: str, new_value: Any):
        params_dict = self.target_dict.setdefault("params", {})
        self.editor.step.set_step_param(
            target_dict=params_dict,
            key=key,
            new_value=new_value,
            name=_("Change Galvo Setting"),
            on_change_callback=lambda: self.step.updated.send(self.step),
        )
