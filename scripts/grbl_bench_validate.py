import argparse
import asyncio
import importlib.util
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEVICE_API_SRC = ROOT / "packages" / "device_api" / "src"
DEVICE_API_PKG = DEVICE_API_SRC / "device_api"


def _load_device_api_module(module_name: str):
    if "device_api" not in sys.modules:
        pkg = types.ModuleType("device_api")
        pkg.__path__ = [str(DEVICE_API_PKG)]
        sys.modules["device_api"] = pkg

    full_name = f"device_api.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    file_path = DEVICE_API_PKG / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo {full_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


interfaces = _load_device_api_module("interfaces")
spooler_mod = _load_device_api_module("spooler")

IConnection = interfaces.IConnection
TransportStatus = interfaces.TransportStatus
GCodeSpooler = spooler_mod.GCodeSpooler


@dataclass
class StepResult:
    name: str
    ok: bool
    details: str
    elapsed_s: float


class MockConnection(IConnection):
    def __init__(self):
        self._is_connected = False
        self._on_received_cb: Optional[Callable[[bytes], None]] = None
        self._on_status_changed_cb: Optional[
            Callable[[TransportStatus, Optional[str]], None]
        ] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        self._is_connected = True
        if self._on_status_changed_cb:
            self._on_status_changed_cb(TransportStatus.CONNECTED, None)
        if self._on_received_cb:
            self._on_received_cb(b"Grbl 1.1h ['$' for help]\n")

    async def disconnect(self) -> None:
        self._is_connected = False
        if self._on_status_changed_cb:
            self._on_status_changed_cb(TransportStatus.DISCONNECTED, None)

    async def send(self, data: bytes) -> None:
        if not self._on_received_cb:
            return

        async def emit(payload: bytes) -> None:
            await asyncio.sleep(0)
            if self._on_received_cb:
                self._on_received_cb(payload)

        await asyncio.sleep(0.01)
        if data == b"?":
            asyncio.create_task(
                emit(b"<Idle|MPos:0.000,0.000,0.000|FS:0,0>\n")
            )
            return

        if data == b"!":
            asyncio.create_task(emit(b"ok\n"))
            asyncio.create_task(
                emit(b"<Hold:0|MPos:0.000,0.000,0.000|FS:0,0>\n")
            )
            return

        if data == b"~":
            asyncio.create_task(emit(b"ok\n"))
            asyncio.create_task(
                emit(b"<Idle|MPos:0.000,0.000,0.000|FS:0,0>\n")
            )
            return

        if data == b"\x18":
            asyncio.create_task(emit(b"ok\n"))
            asyncio.create_task(emit(b"Grbl 1.1h ['$' for help]\n"))
            return

        asyncio.create_task(emit(b"ok\n"))

    @property
    def on_received(self) -> Callable[[bytes], None]:
        return self._on_received_cb  # type: ignore[return-value]

    @on_received.setter
    def on_received(self, callback: Callable[[bytes], None]) -> None:
        self._on_received_cb = callback

    @property
    def on_status_changed(
        self,
    ) -> Callable[[TransportStatus, Optional[str]], None]:
        return self._on_status_changed_cb  # type: ignore[return-value]

    @on_status_changed.setter
    def on_status_changed(
        self, callback: Callable[[TransportStatus, Optional[str]], None]
    ) -> None:
        self._on_status_changed_cb = callback


class BenchRunner:
    def __init__(self, connection: IConnection, timeout_s: float):
        self.connection = connection
        self.timeout_s = timeout_s
        self.spooler = GCodeSpooler(connection)
        self._rx_buffer = b""
        self.received_lines: List[str] = []
        self.connection.on_received = self._on_received

    def _on_received(self, data: bytes) -> None:
        self.spooler._on_data_received(data)
        self._rx_buffer += data
        while b"\n" in self._rx_buffer:
            line_data, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
            line = line_data.decode("utf-8", errors="ignore").strip()
            if line:
                self.received_lines.append(line)

    async def _wait_for(
        self,
        predicate: Callable[[List[str]], bool],
        timeout_s: Optional[float] = None,
    ) -> bool:
        timeout = self.timeout_s if timeout_s is None else timeout_s
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            if predicate(self.received_lines):
                return True
            await asyncio.sleep(0.02)
        return False

    async def run_step(
        self,
        name: str,
        action: Callable[[], asyncio.Future],
    ) -> StepResult:
        start = time.perf_counter()
        try:
            await action()
            return StepResult(
                name=name,
                ok=True,
                details="ok",
                elapsed_s=time.perf_counter() - start,
            )
        except Exception as exc:
            return StepResult(
                name=name,
                ok=False,
                details=str(exc),
                elapsed_s=time.perf_counter() - start,
            )

    async def connect(self) -> None:
        await self.connection.connect()

    async def disconnect(self) -> None:
        await self.connection.disconnect()

    async def validate_handshake(self) -> None:
        ok = await self._wait_for(
            lambda lines: any(line.startswith("Grbl ") for line in lines)
        )
        if not ok:
            raise RuntimeError("Handshake Grbl nao detectado")

    async def validate_status_query(self) -> None:
        await self.spooler.send_command("?", priority=True)
        ok = await self._wait_for(
            lambda lines: any(line.startswith("<") for line in lines)
        )
        if not ok:
            raise RuntimeError("Status report nao recebido apos '?' ")

    async def validate_safe_motion_stream(self) -> None:
        self.spooler.start_job()
        gcode = "\n".join(
            [
                "G21",
                "G90",
                "G0 X0 Y0",
                "G1 X1 Y0 F600",
                "G1 X1 Y1 F600",
                "G1 X0 Y1 F600",
                "G1 X0 Y0 F600",
                "M5",
            ]
        )
        await self.spooler.stream_gcode(gcode)
        ok = await self._wait_for(lambda _lines: self.spooler._rx_buffer_count == 0)
        if not ok:
            raise RuntimeError("Buffer nao drenou para 0 apos stream")

    async def validate_hold_resume(self) -> None:
        await self.spooler.send_command("!", priority=True)
        hold_ok = await self._wait_for(
            lambda lines: any("Hold" in line for line in lines),
            timeout_s=2.0,
        )
        await self.spooler.send_command("~", priority=True)
        idle_ok = await self._wait_for(
            lambda lines: any("Idle" in line for line in lines),
            timeout_s=2.0,
        )
        if not (hold_ok and idle_ok):
            raise RuntimeError("Hold/Resume sem transicao esperada")

    async def validate_soft_reset(self) -> None:
        await self.spooler.cancel()
        ok = await self._wait_for(
            lambda lines: any(line.startswith("Grbl ") for line in lines),
            timeout_s=3.0,
        )
        if not ok:
            raise RuntimeError("Soft reset sem novo banner Grbl")

    async def close(self) -> None:
        self.spooler._command_processor_task.cancel()
        try:
            await self.spooler._command_processor_task
        except asyncio.CancelledError:
            pass


def print_report(results: List[StepResult]) -> None:
    print("\n=== Validacao GRBL de Bancada ===")
    for item in results:
        status = "PASS" if item.ok else "FAIL"
        print(
            f"- {status:4} | {item.name:28} | {item.elapsed_s:5.2f}s"
            f" | {item.details}"
        )

    required = [
        "connect",
        "handshake",
        "status_query",
        "safe_motion_stream",
        "soft_reset",
    ]
    required_ok = all(
        next((x.ok for x in results if x.name == req), False)
        for req in required
    )
    print("\nCriterio de aprovacao minimo:")
    print("- Connect + Handshake + Status + Stream + Soft reset")
    print(f"- Resultado: {'APROVADO' if required_ok else 'REPROVADO'}")


async def run_bench(port: str, baudrate: int, timeout_s: float, dry_run: bool) -> int:
    if dry_run:
        connection: IConnection = MockConnection()
    else:
        transport_mod = _load_device_api_module("transport")
        SerialConnection = transport_mod.SerialConnection

        connection = SerialConnection(port=port, baudrate=baudrate)

    runner = BenchRunner(connection=connection, timeout_s=timeout_s)

    steps: List[Tuple[str, Callable[[], asyncio.Future]]] = [
        ("connect", runner.connect),
        ("handshake", runner.validate_handshake),
        ("status_query", runner.validate_status_query),
        ("safe_motion_stream", runner.validate_safe_motion_stream),
        ("hold_resume", runner.validate_hold_resume),
        ("soft_reset", runner.validate_soft_reset),
    ]

    results: List[StepResult] = []
    try:
        for name, action in steps:
            result = await runner.run_step(name, action)
            results.append(result)
            if not result.ok and name in {
                "connect",
                "handshake",
                "status_query",
            }:
                break
    finally:
        try:
            await runner.disconnect()
        except Exception:
            pass
        await runner.close()

    print_report(results)

    required = {
        "connect",
        "handshake",
        "status_query",
        "safe_motion_stream",
        "soft_reset",
    }
    required_ok = all(
        next((x.ok for x in results if x.name == req), False)
        for req in required
    )
    return 0 if required_ok else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validacao de bancada para fluxo GRBL (device_api)"
    )
    parser.add_argument("--port", default="COM3", help="Porta serial")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa sem hardware usando conexao simulada",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(
        run_bench(
            port=args.port,
            baudrate=args.baudrate,
            timeout_s=args.timeout,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
