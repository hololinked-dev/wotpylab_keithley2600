"""Thing Description (as a Thing Model) of the Keithley 2600 Thing."""

import inspect
from typing import Any

from hololinked.metadata.td.base import WoTSchema
from keithley2600.keithley_driver import Keithley2600 as BuiltinKeithley2600

from wotpylab_keithley2600.keithley2600 import Buffer

SMU = {"type": "string", "enum": ["smua", "smub"]}

LUA_ATTRIBUTE_NAME_SCHEMA = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
LUA_ATTRIBUTE_VALUE_SCHEMA = {"oneOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}]}

RESULT_TABLE = {
    "type": "object",
    "properties": {
        "columns": {"type": "array", "items": {"type": "string"}},
        "units": {"type": "array", "items": {"type": "string"}},
        "data": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "params": {"type": "object"},
    },
}

SWEEP = {
    "t_int": {"type": "number", "unit": "s"},
    "delay": {"type": "number", "unit": "s"},
    "pulsed": {"type": "boolean"},
}


def summary(member: Any) -> str:
    """First paragraph of a docstring of the builtin driver, which leaves out reST directives like `.. warning::`."""
    return WoTSchema.format_doc(inspect.cleandoc(member.__doc__ or "").split("\n\n")[0])


def object_schema(required: bool = True, **properties: dict) -> dict:
    """Object input schema whose keys are the method's keyword arguments."""
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(properties)
    return schema


def array_schema(*names: str) -> dict:
    """Output schema of a tuple of number lists, documented by the names of its entries."""
    return {
        "type": "array",
        "items": {"type": "array", "items": {"type": "number"}},
        "description": f"[{', '.join(names)}]",
    }


def smu_properties(smu: str) -> dict:
    """TSP attributes of one SMU exposed as properties, named by their TSP path (e.g. `smua.source.levelv`)."""
    label = f"SMU {smu[-1].upper()}"
    return {
        f"{smu}.source.output": {
            "title": f"{label} output",
            "description": f"Output state of {label}: 0 off (OUTPUT_OFF), 1 on (OUTPUT_ON), 2 high-Z (OUTPUT_HIGH_Z).",
            "type": "integer",
            "enum": [0, 1, 2],
        },
        f"{smu}.source.levelv": {
            "title": f"{label} source voltage",
            "description": f"Source voltage level of {label}.",
            "type": "number",
            "unit": "V",
        },
        f"{smu}.source.leveli": {
            "title": f"{label} source current",
            "description": f"Source current level of {label}.",
            "type": "number",
            "unit": "A",
        },
        f"{smu}.source.limitv": {
            "title": f"{label} voltage compliance",
            "description": f"Voltage limit (compliance) of {label} when sourcing current.",
            "type": "number",
            "unit": "V",
        },
        f"{smu}.source.limiti": {
            "title": f"{label} current compliance",
            "description": f"Current limit (compliance) of {label} when sourcing voltage.",
            "type": "number",
            "unit": "A",
        },
        f"{smu}.source.rangev": {
            "title": f"{label} source voltage range",
            "description": f"Voltage source range of {label}, setting it turns autorange off.",
            "type": "number",
            "unit": "V",
        },
        f"{smu}.source.autorangev": {
            "title": f"{label} source voltage autorange",
            "description": f"Voltage source autorange of {label}: 0 off (AUTORANGE_OFF), 1 on (AUTORANGE_ON).",
            "type": "integer",
            "enum": [0, 1],
        },
        f"{smu}.measure.nplc": {
            "title": f"{label} integration time",
            "description": f"Integration time of {label} measurements in power line cycles.",
            "type": "number",
        },
    }


TD = {
    "id": "keithley-2600",
    "title": "Keithley 2600",
    "description": summary(BuiltinKeithley2600),
    "properties": {
        "busy": {
            "title": "Busy",
            "description": summary(BuiltinKeithley2600.busy),
            "type": "boolean",
            "readOnly": True,
        },
        "connected": {
            "title": "Connected",
            "description": "True if the VISA connection to the instrument is open, False otherwise.",
            "type": "boolean",
            "readOnly": True,
        },
        # TSP attributes, resolved on the driver at access time (dynamic_attributes=True)
        **smu_properties("smua"),
        **smu_properties("smub"),
    },
    "actions": {
        # connection
        "connect": {
            "title": "Connect",
            "description": summary(BuiltinKeithley2600.connect),
            "output": {
                "type": "boolean",
            },
        },
        "disconnect": {
            "title": "Disconnect",
            "description": summary(BuiltinKeithley2600.disconnect),
        },
        # low level
        "read_error_queue": {
            "title": "Read error queue",
            "description": summary(BuiltinKeithley2600.read_error_queue),
            "output": {
                "type": "array",
                "items": {
                    "type": "array",
                    "description": "[code, message, severity, node]",
                },
            },
        },
        "read_buffer": {
            "title": "Read buffer",
            "description": summary(BuiltinKeithley2600.read_buffer),
            "input": {
                "type": "string",
                "enum": [buffer.value for buffer in Buffer],
            },
            "output": {
                "type": "array",
                "items": {"type": "number"},
            },
        },
        "create_lua_attr": {
            "title": "Create Lua attribute",
            "description": summary(BuiltinKeithley2600.create_lua_attr),
            "input": object_schema(name=LUA_ATTRIBUTE_NAME_SCHEMA, value=LUA_ATTRIBUTE_VALUE_SCHEMA),
        },
        "delete_lua_attr": {
            "title": "Delete Lua attribute",
            "description": summary(BuiltinKeithley2600.delete_lua_attr),
            "input": LUA_ATTRIBUTE_NAME_SCHEMA,
        },
        "send_trigger": {
            "title": "Send trigger",
            "description": summary(BuiltinKeithley2600.send_trigger),
        },
        # source and measure
        "set_integration_time": {
            "title": "Set integration time",
            "description": summary(BuiltinKeithley2600.set_integration_time),
            "input": object_schema(smu=SMU, t_int={"type": "number", "unit": "s"}),
        },
        "apply_voltage": {
            "title": "Apply voltage",
            "description": summary(BuiltinKeithley2600.apply_voltage),
            "input": object_schema(smu=SMU, voltage={"type": "number", "unit": "V"}),
        },
        "apply_current": {
            "title": "Apply current",
            "description": summary(BuiltinKeithley2600.apply_current),
            "input": object_schema(smu=SMU, curr={"type": "number", "unit": "A"}),
        },
        "measure_voltage": {
            "title": "Measure voltage",
            "description": summary(BuiltinKeithley2600.measure_voltage),
            "input": SMU,
            "output": {"type": "number", "unit": "V"},
        },
        "measure_current": {
            "title": "Measure current",
            "description": summary(BuiltinKeithley2600.measure_current),
            "input": SMU,
            "output": {"type": "number", "unit": "A"},
        },
        "ramp_to_voltage": {
            "title": "Ramp to voltage",
            "description": summary(BuiltinKeithley2600.ramp_to_voltage),
            "input": {
                **object_schema(
                    smu=SMU,
                    target_volt={"type": "number", "unit": "V"},
                    delay={"type": "number", "unit": "s"},
                    step_size={"type": "number", "unit": "V"},
                ),
                "required": ["smu", "target_volt"],
            },
        },
        # sweeps
        "voltage_sweep_single_smu": {
            "title": "Voltage sweep (single SMU)",
            "description": summary(BuiltinKeithley2600.voltage_sweep_single_smu),
            "input": object_schema(smu=SMU, smu_sweeplist={"type": "array", "items": {"type": "number"}}, **SWEEP),
            "output": array_schema("v_smu", "i_smu"),
        },
        "voltage_sweep_dual_smu": {
            "title": "Voltage sweep (dual SMU)",
            "description": summary(BuiltinKeithley2600.voltage_sweep_dual_smu),
            "input": object_schema(
                smu1=SMU,
                smu2=SMU,
                smu1_sweeplist={"type": "array", "items": {"type": "number"}},
                smu2_sweeplist={"type": "array", "items": {"type": "number"}},
                **SWEEP,
            ),
            "output": array_schema("v_smu1", "i_smu1", "v_smu2", "i_smu2"),
        },
        "transfer_measurement": {
            "title": "Transfer measurement",
            # the builtin docstring describes its FETResultTable return, this Thing returns a plain table
            "description": "Records a transfer curve with forward and reverse sweeps and returns the results as a table.",
            "input": object_schema(
                smu_gate=SMU,
                smu_drain=SMU,
                vg_start={"type": "number", "unit": "V"},
                vg_stop={"type": "number", "unit": "V"},
                vg_step={"type": "number", "unit": "V"},
                vd_list={"type": "array", "items": {"type": "number"}},
                **SWEEP,
            ),
            "output": RESULT_TABLE,
        },
        "output_measurement": {
            "title": "Output measurement",
            # same as transfer_measurement
            "description": "Records an output curve with forward and reverse sweeps and returns the results as a table.",
            "input": object_schema(
                smu_gate=SMU,
                smu_drain=SMU,
                vd_start={"type": "number", "unit": "V"},
                vd_stop={"type": "number", "unit": "V"},
                vd_step={"type": "number", "unit": "V"},
                vg_list={"type": "array", "items": {"type": "number"}},
                **SWEEP,
            ),
            "output": RESULT_TABLE,
        },
        "abort": {
            # not a driver method: sets the abort flag the sweeps check
            "title": "Abort",
            "description": "Aborts a running voltage sweep, transfer or output measurement.",
        },
        # misc
        "play_chord": {
            "title": "Play chord",
            "description": summary(BuiltinKeithley2600.play_chord),
            "input": object_schema(
                required=False,
                notes={"type": "array", "items": {"type": "string"}},
                durations={"oneOf": [{"type": "number", "unit": "s"}, {"type": "array", "items": {"type": "number"}}]},
            ),
        },
    },
}
