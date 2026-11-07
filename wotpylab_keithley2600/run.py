"""
Command line interface of the Keithley 2600 Thing.

uv run wotpylab-keithley2600 generate-td --output keithley-2600.json   # write the TD as JSON
uv run wotpylab-keithley2600 serve --td keithley-2600.json              # serve the Thing over HTTP
(or `uv run python -m wotpylab_keithley2600.run ...`)
"""

import argparse
import getpass
import json
import os
import ssl

from dataclasses import dataclass, fields
from typing import Any

from hololinked.metadata.td import ThingModel
from hololinked.server import BaseProtocolServer, run
from hololinked.server.http import HTTPServer
from hololinked.server.security import (
    APIKeySecurity,
    Argon2BasicSecurity,
    BcryptBasicSecurity,
    OIDCSecurity,
    Security,
)
from hololinked.server.zmq import ZMQServer

from wotpylab_keithley2600.keithley2600 import Keithley2600
from wotpylab_keithley2600.td import TD


PROTOCOLS = ["http", "zmq"]
SECURITY_SCHEMES = ["basic", "apikey", "oidc"]
PASSWORD_HASHERS = {"argon2": Argon2BasicSecurity, "bcrypt": BcryptBasicSecurity}


@dataclass
class Keithley2600Arguments:
    """Arguments of `Keithley2600()`."""

    # 192.0.2.1 is a reserved documentation address (no real host): connect() fails
    # fast and the instance is created with connected=False, so no physical device is needed
    visa_address: str = "TCPIP0::192.0.2.1::INSTR"
    visa_library: str = "@py"
    raise_keithley_errors: bool = False


@dataclass
class HTTPArguments:
    """Arguments of `HTTPServer()`."""

    port: int = 8080
    address: str = "0.0.0.0"
    allowed_clients: list[str] | None = None
    cors: bool = True  # hololinked's default, global_config.ALLOW_CORS
    certfile: str | None = None
    keyfile: str | None = None

    def ssl_context(self) -> ssl.SSLContext | None:
        """SSL context from the certificate (and key) files, None to serve plain HTTP."""
        if not self.certfile:
            return None
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
        return context


@dataclass
class ZMQArguments:
    """Arguments of `ZMQServer()`."""

    server_id: str = "keithley-2600-server"
    access_points: tuple[str, ...] = ("IPC",)


@dataclass
class SecurityArguments:
    """Arguments of the security scheme of the server."""

    security: str | None = None  # no security
    username: str | None = None
    password_hasher: str = "argon2"  # recommended by hololinked, bcrypt needs less memory
    apikey_name: str | None = None
    apikey_file: str | None = None  # hololinked's apikeys.json in its secrets directory
    # OIDC options override the values of the config file, None means not given
    oidc_config_file: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None  # not checked if not given
    oidc_jwks_url: str | None = None  # discovered from the issuer if not given
    oidc_allowed_roles: list[str] | None = None  # any role if not given
    oidc_verify_ssl: bool | None = None  # verified if not given


def security_schemes(security_arguments: SecurityArguments) -> list[Security] | None:
    """Security schemes of the server, None for no security."""
    if security_arguments.security is None:
        return None
    if security_arguments.security == "basic":
        if not security_arguments.username:
            raise ValueError("basic security needs a --username")
        # prompted, so that the password is neither in the shell history nor in the process list
        password = getpass.getpass(f"Password of {security_arguments.username}: ")
        basic_security = PASSWORD_HASHERS[security_arguments.password_hasher]
        return [basic_security(username=security_arguments.username, password=password)]
    if security_arguments.security == "apikey":
        if not security_arguments.apikey_name:
            raise ValueError("apikey security needs an --apikey-name")
        apikey_name = security_arguments.apikey_name
        apikey_file = (
            os.path.abspath(security_arguments.apikey_file) if security_arguments.apikey_file else "apikeys.json"
        )
        apikey_security = APIKeySecurity(name=apikey_name, file=apikey_file)
        if apikey_security.record is None:  # ty: ignore[unresolved-attribute]
            raise ValueError(f"no API key named {apikey_name!r} in {apikey_file}")
        return [apikey_security]
    if security_arguments.security == "oidc":
        oidc_config: dict[str, Any] = {}
        if security_arguments.oidc_config_file:
            with open(security_arguments.oidc_config_file, encoding="utf-8") as file:
                oidc_config = json.load(file)
        options = {
            "issuer": security_arguments.oidc_issuer,
            "audience": security_arguments.oidc_audience,
            "jwks_url": security_arguments.oidc_jwks_url,
            "allowed_roles": security_arguments.oidc_allowed_roles,
            "verify_ssl": security_arguments.oidc_verify_ssl,
        }
        oidc_config.update({key: value for key, value in options.items() if value is not None})
        if not oidc_config.get("issuer"):
            raise ValueError("oidc security needs an issuer, from --oidc-issuer or --oidc-config-file")
        oidc_config.setdefault("audience", None)  # required argument of OIDCSecurity()
        # contacts the provider at startup to discover its signing keys
        return [OIDCSecurity(**oidc_config)]
    raise ValueError(f"unknown security scheme {security_arguments.security!r}")


def argument_dataclass(cls: type, arguments: dict[str, Any]) -> Any:
    """Create the dataclass from its fields in the parsed arguments, and remove them from the arguments."""
    return cls(**{field.name: arguments.pop(field.name) for field in fields(cls)})


def generate_td(output: str) -> None:
    """Write the TD (as a Thing Model) as JSON to a file."""
    with open(output, "w", encoding="utf-8") as file:
        json.dump(TD, file, indent=4)


def protocol_server(
    protocol: str,
    http_arguments: HTTPArguments,
    security_arguments: SecurityArguments,
    zmq_arguments: ZMQArguments,
) -> BaseProtocolServer:
    """Server of the protocol, created from the arguments of that protocol."""
    if protocol == "http":
        return HTTPServer(
            port=http_arguments.port,
            address=http_arguments.address,
            allowed_clients=http_arguments.allowed_clients,
            ssl_context=http_arguments.ssl_context(),
            config={"cors": http_arguments.cors},
            security_schemes=security_schemes(security_arguments=security_arguments),
        )
    if protocol == "zmq":
        if security_arguments.security is not None:
            raise ValueError("security schemes are supported over HTTP only")
        return ZMQServer(id=zmq_arguments.server_id, access_points=list(zmq_arguments.access_points))
    raise ValueError(f"unknown protocol {protocol!r}")


def serve(
    td: str | None,
    id: str,
    keithley_arguments: Keithley2600Arguments,
    protocol: str,
    http_arguments: HTTPArguments,
    security_arguments: SecurityArguments,
    zmq_arguments: ZMQArguments,
) -> None:
    """Start the device and serve it over a protocol."""
    thing_model = ThingModel.from_file(td) if td else ThingModel.from_metadata(TD)
    device = thing_model.produce(
        Keithley2600(
            visa_address=keithley_arguments.visa_address,
            visa_library=keithley_arguments.visa_library,
            raise_keithley_errors=keithley_arguments.raise_keithley_errors,
        ),
        id=id,
        # TD properties named by their TSP path (smua.source.levelv) are resolved on the driver at access time
        dynamic_attributes=True,
    )
    server = protocol_server(
        protocol=protocol,
        http_arguments=http_arguments,
        security_arguments=security_arguments,
        zmq_arguments=zmq_arguments,
    )
    server.add_thing(device)
    run(server)


COMMANDS = {
    "generate-td": generate_td,
    "serve": serve,
}


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keithley 2600 Thing")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")
    parsers = {name: subparsers.add_parser(name, help=command.__doc__) for name, command in COMMANDS.items()}

    parsers["generate-td"].add_argument("--output", default="keithley-2600.json", help="file to write the TD to")

    parsers["serve"].add_argument("--td", help="TD file to serve, the TD of td.py if not given")
    parsers["serve"].add_argument("--id", default="keithley-2600", help="id of the Thing")
    parsers["serve"].add_argument("--protocol", choices=PROTOCOLS, default="http", help="protocol to serve with")

    # the defaults come from the dataclasses
    keithley = parsers["serve"].add_argument_group("Keithley2600")
    keithley.add_argument("--visa-address", default=Keithley2600Arguments.visa_address, help="VISA address")
    keithley.add_argument(
        "--visa-library",
        default=Keithley2600Arguments.visa_library,
        help="VISA library, @py for pyvisa-py",
    )
    keithley.add_argument(
        "--raise-keithley-errors",
        action="store_true",
        help="raise errors of the instrument as Python errors",
    )

    http = parsers["serve"].add_argument_group("HTTP")
    http.add_argument("--port", type=int, default=HTTPArguments.port, help="port")
    http.add_argument(
        "--address",
        default=HTTPArguments.address,
        help="address, 0.0.0.0 for all interfaces, 127.0.0.1 for localhost",
    )
    http.add_argument(
        "--allowed-clients",
        nargs="+",
        default=HTTPArguments.allowed_clients,
        help="IP addresses of the only clients served, others are rejected with 403",
    )
    http.add_argument(
        "--cors",
        action=argparse.BooleanOptionalAction,
        default=HTTPArguments.cors,
        help="set CORS headers",
    )
    http.add_argument("--certfile", default=HTTPArguments.certfile, help="certificate file, serves HTTPS if given")
    http.add_argument("--keyfile", default=HTTPArguments.keyfile, help="private key file of the certificate")

    security = parsers["serve"].add_argument_group("Security")
    security.add_argument(
        "--security",
        choices=SECURITY_SCHEMES,
        default=SecurityArguments.security,
        help="security scheme, none if not given",
    )
    security.add_argument(
        "--username",
        default=SecurityArguments.username,
        help="username of basic security, the password is prompted for",
    )
    security.add_argument(
        "--password-hasher",
        choices=PASSWORD_HASHERS,
        default=SecurityArguments.password_hasher,
        help="hash of the password of basic security",
    )
    security.add_argument(
        "--apikey-name",
        default=SecurityArguments.apikey_name,
        help="name of the API key of apikey security",
    )
    security.add_argument(
        "--apikey-file",
        default=SecurityArguments.apikey_file,
        help="file the API keys are stored in, apikeys.json in hololinked's secrets directory if not given",
    )
    security.add_argument(
        "--oidc-config-file",
        default=SecurityArguments.oidc_config_file,
        help="JSON file with the arguments of OIDCSecurity (issuer, audience, ...), the options below override it",
    )
    security.add_argument(
        "--oidc-issuer",
        default=SecurityArguments.oidc_issuer,
        help="issuer URL of the OIDC provider (iss claim)",
    )
    security.add_argument(
        "--oidc-audience",
        default=SecurityArguments.oidc_audience,
        help="expected audience (aud claim), often the client id, not checked if not given",
    )
    security.add_argument(
        "--oidc-jwks-url",
        default=SecurityArguments.oidc_jwks_url,
        help="URL of the signing keys, discovered from the issuer if not given",
    )
    security.add_argument(
        "--oidc-allowed-roles",
        nargs="+",
        default=SecurityArguments.oidc_allowed_roles,
        help="roles of which the token must have one, any role if not given",
    )
    security.add_argument(
        "--oidc-verify-ssl",
        action=argparse.BooleanOptionalAction,
        default=SecurityArguments.oidc_verify_ssl,
        help="verify the SSL certificate of the OIDC provider",
    )

    zmq = parsers["serve"].add_argument_group("ZMQ")
    zmq.add_argument("--server-id", default=ZMQArguments.server_id, help="id of the ZMQ server")
    zmq.add_argument(
        "--access-points",
        nargs="+",
        default=ZMQArguments.access_points,
        help="IPC, INPROC, TCP or a TCP socket address like tcp://*:5555 (events are published on the next port)",
    )
    return parser


def main() -> None:
    """Entry point of the `wotpylab-keithley2600` command (see `[project.scripts]` in pyproject.toml)."""
    arguments = vars(argument_parser().parse_args())
    command = arguments.pop("command")
    if command == "serve":
        arguments["keithley_arguments"] = argument_dataclass(cls=Keithley2600Arguments, arguments=arguments)
        arguments["http_arguments"] = argument_dataclass(cls=HTTPArguments, arguments=arguments)
        arguments["security_arguments"] = argument_dataclass(cls=SecurityArguments, arguments=arguments)
        arguments["zmq_arguments"] = argument_dataclass(cls=ZMQArguments, arguments=arguments)
    # the remaining arguments are the keyword arguments of the command
    COMMANDS[command](**arguments)


if __name__ == "__main__":
    main()
