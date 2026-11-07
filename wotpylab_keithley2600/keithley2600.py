"""The keithley2600 driver with JSON-serializable arguments and results, to implement the TD in `td.py`."""

from enum import StrEnum
from typing import Any

from keithley2600.keithley_driver import Keithley2600 as BuiltinKeithley2600
from keithley2600.keithley_driver import KeithleyClass
from keithley2600.result_table import ResultTable


class Buffer(StrEnum):
    """Non-volatile reading buffers of the SMUs, by their TSP path."""

    SMUA_NVBUFFER1 = "smua.nvbuffer1"
    SMUA_NVBUFFER2 = "smua.nvbuffer2"
    SMUB_NVBUFFER1 = "smub.nvbuffer1"
    SMUB_NVBUFFER2 = "smub.nvbuffer2"


def table_to_dict(table: ResultTable) -> dict:
    return {
        "columns": table.column_names,
        "units": table.column_units,
        "data": table.data.tolist(),
        "params": table.params,
    }


class Keithley2600(BuiltinKeithley2600):
    # The builtin driver with serializable arguments and return values.
    # Dont add classdoc.
    # We have two options with respect to exposing this driver, the easier one being going code-first.
    # That would look like:
    # >> class Keithley2600(BuiltinKeithley2600, Thing):
    # >>     def __init__(self, id: str, visa_address: str, visa_library: str = "@py", raise_keithley_errors: bool = False, **kwargs)
    # >>         self.keithley = BuiltinKeithley2600(visa_address, visa_library, raise_keithley_errors, **kwargs)
    # >>         super().__init__(id=id)
    # >>
    # >>     # redefine builtin methods to use self.keithley if needed, for example
    # >>     def apply_voltage(self, smu: str | KeithleyClass, voltage: float) -> None:
    # >>         self.keithley.apply_voltage(self.smu(smu), voltage)
    #
    # But this approach requires redefining all methods to delegate to self.keithley, moreover, we need to override
    # getattr to delegate all the dynamic LUA stuff one level below, which is already done in the builtin driver.
    #
    # Instead we are trying to reuse the driver class for all the dynamic attributes and go API first by simply
    # defining those dynamic attributes in the TD API directly. In this way, all dynamic stuff lives in the API.
    #
    # Both approaches are valid.

    # ---- low level ----

    def read_buffer(self, buffer: str | KeithleyClass) -> list[float]:
        return super().read_buffer(self._buffer(buffer))

    def create_lua_attr(self, name: str | int, value: Any) -> None:
        super().create_lua_attr(name, value)  # returned accessor is not serializable

    # ---- source and measure ----

    def set_integration_time(self, smu: str | KeithleyClass, t_int: float) -> None:
        super().set_integration_time(self.smu(smu), t_int)

    def apply_voltage(self, smu: str | KeithleyClass, voltage: float) -> None:
        super().apply_voltage(self.smu(smu), voltage)

    def apply_current(self, smu: str | KeithleyClass, curr: float) -> None:
        super().apply_current(self.smu(smu), curr)

    def measure_voltage(self, smu: str | KeithleyClass) -> float:
        return super().measure_voltage(self.smu(smu))

    def measure_current(self, smu: str | KeithleyClass) -> float:
        return super().measure_current(self.smu(smu))

    def ramp_to_voltage(
        self,
        smu: str | KeithleyClass,
        target_volt: float,
        delay: float = 0.1,
        step_size: float = 1,
    ) -> None:
        super().ramp_to_voltage(smu=self.smu(smu), target_volt=target_volt, delay=delay, step_size=step_size)

    # ---- sweeps ----

    def voltage_sweep_single_smu(
        self,
        smu: str | KeithleyClass,
        smu_sweeplist: list[float],
        t_int: float,
        delay: float,
        pulsed: bool,
    ) -> tuple[list[float], list[float]]:
        return super().voltage_sweep_single_smu(
            smu=self.smu(smu),
            smu_sweeplist=smu_sweeplist,
            t_int=t_int,
            delay=delay,
            pulsed=pulsed,
        )

    def voltage_sweep_dual_smu(
        self,
        smu1: str | KeithleyClass,
        smu2: str | KeithleyClass,
        smu1_sweeplist: list[float],
        smu2_sweeplist: list[float],
        t_int: float,
        delay: float,
        pulsed: bool,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        # keep the builtin tuple return: transfer/output_measurement unpack it internally
        return super().voltage_sweep_dual_smu(
            smu1=self.smu(smu1),
            smu2=self.smu(smu2),
            smu1_sweeplist=smu1_sweeplist,
            smu2_sweeplist=smu2_sweeplist,
            t_int=t_int,
            delay=delay,
            pulsed=pulsed,
        )

    def transfer_measurement(
        self,
        smu_gate: str | KeithleyClass,
        smu_drain: str | KeithleyClass,
        vg_start: float,
        vg_stop: float,
        vg_step: float,
        vd_list: list[float],
        t_int: float,
        delay: float,
        pulsed: bool,
    ) -> dict:
        table = super().transfer_measurement(
            smu_gate=self.smu(smu_gate),
            smu_drain=self.smu(smu_drain),
            vg_start=vg_start,
            vg_stop=vg_stop,
            vg_step=vg_step,
            vd_list=vd_list,
            t_int=t_int,
            delay=delay,
            pulsed=pulsed,
        )
        return table_to_dict(table)

    def output_measurement(
        self,
        smu_gate: str | KeithleyClass,
        smu_drain: str | KeithleyClass,
        vd_start: float,
        vd_stop: float,
        vd_step: float,
        vg_list: list[float],
        t_int: float,
        delay: float,
        pulsed: bool,
    ) -> dict:
        table = super().output_measurement(
            smu_gate=self.smu(smu_gate),
            smu_drain=self.smu(smu_drain),
            vd_start=vd_start,
            vd_stop=vd_stop,
            vd_step=vd_step,
            vg_list=vg_list,
            t_int=t_int,
            delay=delay,
            pulsed=pulsed,
        )
        return table_to_dict(table)

    def abort(self) -> None:
        self.abort_event.set()

    # ---- helpers (underscore: never bound to the TD) ----

    def smu(self, smu: str | KeithleyClass) -> KeithleyClass:
        if isinstance(smu, KeithleyClass):
            return smu
        if smu not in ("smua", "smub"):
            raise ValueError(f"unknown SMU {smu!r}")
        return getattr(self, smu)

    def _buffer(self, buffer: str | KeithleyClass) -> KeithleyClass:
        if isinstance(buffer, KeithleyClass):
            return buffer
        smu, name = Buffer(buffer).split(".")  # ValueError for an unknown buffer
        return getattr(self.smu(smu), name)
