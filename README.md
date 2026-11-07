# wotpylab_keithley2600

A remotely accessible implementation of Keithley 2600B series source measure units (SMUs),
based on [W3C Web of Things](https://www.w3.org/WoT/) and [hololinked](https://hololinked.dev).

Supported:

- HTTP & ZMQ protocols
- username-password, API key and OIDC security schemes
- properties and commands as defined on the SMU

Based on the keithley2600 driver. Documentation of the driver is available at
- [https://github.com/OE-FET/keithley2600](https://github.com/OE-FET/keithley2600)
- [https://keithley2600.readthedocs.io](https://keithley2600.readthedocs.io)

> Current Status: *Untested*. Users wanted. Please write to info@hololinked.dev or jump into the [discord server](https://discord.com/invite/kEz87zqQXh).

## Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Serve the instrument](#serve-the-instrument)
- [The Thing Description](#the-thing-description)
- [Protocols](#protocols)
- [Security](#security)
- [Use with AI agents](#ai-agents)
- [About the driver](#about-the-driver)
- [System requirements](#system-requirements)
- [Documentation](#documentation)

## Installation

Install from PyPI by running
```console
$ pip install wotpylab_keithley2600
```

or the latest development version from GitHub:
```console
$ pip install git+https://github.com/hololinked-dev/wotpylab_keithley2600.git
```

## Quickstart

CLI is the easiest starting point. It has two commands, `serve` and `generate-td`:

```console
$ wotpylab_keithley2600 --help
$ wotpylab_keithley2600 serve --help
```

From a git clone of this repository, prefix the commands with `uv run`, or use
`python -m wotpylab_keithley2600.run` instead of `wotpylab_keithley2600`:

```console
$ uv run wotpylab_keithley2600 --help
$ uv run python -m wotpylab_keithley2600.run --help
```

## Serve the instrument

Give the VISA address of your Keithley:

```console
$ wotpylab_keithley2600 serve --id keithley-2600 --visa-address TCPIP0::192.168.2.121::INSTR
```

HTTP is the default protocol and the instrument will be served on port 8080 with the Thing ID `keithley-2600`. A so-called
*Thing Description* lists every property and action (i.e. attributes and commands, whatever you name them),
with the URLs to read, write and invoke them:

```
http://localhost:8080/keithley-2600/resources/wot-td
# OR
http://localhost:8080/keithley-2600/resources/wot-td?ignore_errors=true
```

The server connects to the instrument when it starts. If the instrument is not reachable then, the server
still starts and its properties return a connection error. Invoke the `connect` action once the instrument is reachable.

Keithley options:

| Option | Default | Description |
|---|---|---|
| `--visa-address` | a placeholder, no instrument | VISA address of the instrument |
| `--visa-library` | `@py` (PyVISA-py) | VISA library, see [Backend selection](#backend-selection) |
| `--raise-keithley-errors` | off | raise errors of the instrument as Python errors |
| `--id` | `keithley-2600` | ID of the Thing, part of every URL |

#### Example HTTP endpoints for properties and actions

Properties named after a TSP attribute, like `smua.source.levelv`, read and write that
attribute on the instrument. For example, over HTTP:

```console
$ curl http://localhost:8080/keithley-2600/smua.source.levelv
$ curl -X PUT -H "Content-Type: application/json" -d 5 http://localhost:8080/keithley-2600/smua.source.levelv
$ curl -X POST -H "Content-Type: application/json" -d '{"smu": "smua", "voltage": 5}' http://localhost:8080/keithley-2600/apply-voltage
```

SMUs and buffers are given by name (`"smua"`, `"smua.nvbuffer1"`). The Thing Description
is the reference for the names, the inputs and the outputs of all interactions.

## The Thing Description

The Thing Description (as a Thing Model) is written in `wotpylab_keithley2600/td.py`.
To read more about Thing Descriptions, see:

- [the readme of hololinked](https://github.com/hololinked-dev/hololinked)
- [the W3C website](https://www.w3.org/WoT/developers/documentation)
- [the specification](https://www.w3.org/TR/wot-thing-description11/)

To change the Thing Description without changing the code, write it to a file, edit the file and serve that file:

```console
$ wotpylab_keithley2600 generate-td --output keithley-2600.json
# add properties and actions to keithley-2600.json
$ wotpylab_keithley2600 serve --td keithley-2600.json --visa-address TCPIP0::192.168.2.121::INSTR
```

To expose another TSP attribute, add a property named by its path to `"properties"`, for example
the current measurement range of SMU A, `smua.measure.rangei`:

```json
{
    "properties": {
        "smua.measure.rangei": {
            "title": "SMU A current measure range",
            "description": "Current measurement range of SMU A, setting it turns autorange off.",
            "type": "number",
            "unit": "A"
        }
    }
}
```

A property without `"readOnly": true` can be read and written. The name must be the TSP path as in the
reference manual of the instrument.

The TSP attributes, which the underlying keithley2600 driver loads dynamically from the instrument, are not exposed
by default. You need to list them in the Thing Description. This way you also control what is exposed and what is not.

## Protocols

Choose the protocol with `--protocol`, `http` by default.

### HTTP options

| Option | Default | Description |
|---|---|---|
| `--port` | `8080` | port |
| `--address` | `0.0.0.0` (all interfaces) | address to bind to, `127.0.0.1` for this computer only |
| `--allowed-clients IP [IP ...]` | all | serve only these clients, reject others with 403 |
| `--cors` / `--no-cors` | on | set CORS headers |
| `--certfile`, `--keyfile` | none | certificate and private key, serves HTTPS if given |

### ZMQ options

| Option | Default | Description |
|---|---|---|
| `--server-id` | `keithley-2600-server` | ID of the ZMQ server |
| `--access-points AP [AP ...]` | `IPC` | `IPC`, `INPROC`, `TCP` or a TCP socket address like `tcp://*:5555` |

```console
$ wotpylab_keithley2600 serve --protocol zmq --access-points IPC tcp://*:5555
```

Over TCP, events are published on the next port (5556 in this example).

## Security

Security schemes are supported over HTTP only. Choose one with `--security`:

**Username and password** (`basic`) 

The password is asked for when the server starts,
so that it is not stored in the shell history:

```console
$ wotpylab_keithley2600 serve --security basic --username lab
Password of lab:
```

Clients send `Authorization: Basic <base64 of username:password>`. The password is stored
as an Argon2 hash; use `--password-hasher bcrypt` for less memory.

**API key** (`apikey`)

Create the key once with hololinked:

```python
import os
from hololinked.server.security import APIKeySecurity

file = os.path.abspath("apikeys.json")
APIKeySecurity(name="lab", file=file).create(file=file)
```
The API key will be printed once. Store it in a safe place to provide to the client. It is valid for 30 days by
default; pass `validity_period_minutes` to `create()` to change that. Then serve with the name of the key and the
file it is stored in:

```console
$ wotpylab_keithley2600 serve --security apikey --apikey-name lab --apikey-file apikeys.json
```

Clients send `X-API-Key: <key>`.

**OIDC** (`oidc`)

Give the issuer of your OIDC provider, for example Keycloak:

```console
$ wotpylab_keithley2600 serve --security oidc --oidc-issuer https://keycloak.example.com/realms/lab --oidc-audience keithley --oidc-allowed-roles device-admin
```

or put the settings in a JSON file, whose keys are the arguments of hololinked's
`OIDCSecurity`:

```json
{
    "issuer": "https://keycloak.example.com/realms/lab",
    "audience": "keithley",
    "allowed_roles": ["device-admin"]
}
```

```console
$ wotpylab_keithley2600 serve --security oidc --oidc-config-file oidc.json
```

Options given on the command line override the file. Clients send
`Authorization: Bearer <access token>`. The server contacts the provider when it starts, to
get its signing keys.

## AI Agents

AI agents can operate the instrument through the same API. To set this up:

- **Serve over HTTP** so that the agent can reach the instrument with plain HTTP requests.
- **Give the agent the Thing Description** (`http://localhost:8080/keithley-2600/resources/wot-td`). It lists every
  property and action with its description, input and output schemas, units and the URL and HTTP method to call,
  which is what an agent needs to turn them into tools.
- **Use an agent that is good at tool calling**, as each property read or write and each action invocation is a tool call
  with JSON input and output.

Keep in mind that the agent controls a real instrument that sources voltage and current. Expose only the
properties and actions it needs in the Thing Description, and use a security scheme so that only the agent and
the people you choose can reach it.

## About The Driver

*From the original authors:*

This driver provides access to base commands and higher level functions such as IV
measurements, transfer and output curves, etc. Base commands replicate the functionality
and syntax from the Keithley's internal TSP Lua functions. This is possible because the
Lua programming language has a very limited syntax which can be represented by a subset
of Python syntax.

All Keithley commands are dynamically queried from the Keithley itself after a
successful connection. This means that essentially all Keithley instruments which use
TSP scripting are supported and any commands introduced in the future will be recognised
automatically (barring changes to the Lua syntax itself). Please refer to the respective
reference manuals for a list of commands available on a particular model, for instance the
[Keithley 2600B reference manual](https://www.tek.com/keithley-source-measure-units/smu-2600b-series-sourcemeter-manual-8).

This dynamic approach however means that most attributes will only be defined after
connecting to an instrument. Several higher level functions for current-voltage sweeps
are defined by the driver itself and may use functionality which is not available on
some models. They have been tested with a Keithley 2612B.

**Warning**: There are currently no checks for allowed arguments by the driver itself.
Passing invalid arguments to a Keithley command will fail silently in Python but will
display an error message on the Keithley itself. To enable command checking, set the
keyword argument `raise_keithley_errors = True` in the constructor (`--raise-keithley-errors`
in the CLI). When set, most
Keithley errors will be raised as Python errors. This is done by reading the Keithley's
error queue after every command and will therefore result in some communication
overhead.

### Backend selection

keithley2600 uses [PyVISA](https://pyvisa.readthedocs.io/) to connect to instruments.
PyVISA supports both proprietary IVI libraries such as NI-VISA, Keysight VISA, R&S VISA,
tekVISA etc. and the purely Python backend [PyVISA-py](https://pyvisa-py.readthedocs.io/en/latest/).
You can select a specific backend by giving its path to the `Keithley2600` constructor
in the `visa_library` argument. For example:

```python
from keithley2600 import Keithley2600

k = Keithley2600('TCPIP0::192.168.2.121::INSTR', visa_library='/usr/lib/libvisa.so.7')
```

keithley2600 defaults to using the PyVISA-py backend, selected by `visa_library='@py'`,
since this is only a pip-install away. If you pass an empty string, keithley2600 will
use an installed IVI library if it can find one in standard locations or fall back to
PyVISA-py otherwise.

You can find more information about selecting the backend in the
[PyVISA docs](https://pyvisa.readthedocs.io/en/latest/introduction/configuring.html).

## System requirements

- Python 3.11 or higher
- On Python 3.13 and higher, the `xdrlib` module, which the keithley2600 driver imports, is no longer in the
  standard library. The `standard-xdrlib` backport is installed for it.

## Documentation

* hololinked documentation: [https://docs.hololinked.dev](https://docs.hololinked.dev)

* hololinked website: [https://hololinked.dev](https://hololinked.dev)

* hololinked Discord server: [https://discord.com/invite/kEz87zqQXh](https://discord.com/invite/kEz87zqQXh)

* API documentation of keithley2600: [https://keithley2600.readthedocs.io/en/latest/](https://keithley2600.readthedocs.io/en/latest/)

* Keithley 2600 reference manual with all commands: [https://www.tek.com/keithley-source-measure-units/smu-2600b-series-sourcemeter-manual-8](https://www.tek.com/keithley-source-measure-units/smu-2600b-series-sourcemeter-manual-8)
