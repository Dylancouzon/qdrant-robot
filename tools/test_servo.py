"""Exercise servo write ordering, bounded movement, and failed shutdown without hardware."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from robot import servo
from tools import servo as cli
import sys


class Packet:
    """Simulate a servo that immediately moves to its goal when torque is enabled."""

    def __init__(self):
        self.memory = {9: 0, 11: 4095, 33: 0, 40: 0, 42: 0, 48: 1000,
                       56: 2048, 62: 50, 63: 27, 65: 0, 66: 0}
        self.writes, self.positions = [], []
        self.fail_at = None

    def read1ByteTxRx(self, _port, _id, address):
        return self.memory.get(address, 0), 0, 0

    read2ByteTxRx = read1ByteTxRx

    def write1ByteTxRx(self, _port, _id, address, value):
        self.writes.append((address, value))
        self.memory[address] = value
        if address == 42:
            self.memory[40] = 1  # Firmware engages torque when a goal is primed.
        if self.memory[40] and address in (40, 42):
            self.memory[56] = self.memory[42]
            self.positions.append(self.memory[56])
        # A lost acknowledgement can happen AFTER the servo has acted.
        return (-6, 0) if (address, value) == self.fail_at else (0, 0)

    write2ByteTxRx = write1ByteTxRx

    @staticmethod
    def getTxRxResult(_result):
        return "Communication timeout"

    @staticmethod
    def getRxPacketError(_error):
        return "Hardware fault"


@pytest.fixture
def device():
    packet = Packet()
    return servo.Servo(SimpleNamespace(is_using=False), packet, 1), packet


def test_status_is_read_only(device):
    motor, packet = device
    assert motor.status()["position"] == 2048
    assert not packet.writes


@pytest.mark.parametrize("degrees", [0, 11, -11, float("nan"), float("inf"), 0.0001])
def test_invalid_angle_writes_nothing(device, degrees):
    motor, packet = device
    with pytest.raises(ValueError):
        motor.nudge(degrees)
    assert not packet.writes


@pytest.mark.parametrize("address,value", [(33, 1), (62, 120), (65, 1), (66, 1), (63, 60)])
def test_unsafe_state_writes_nothing(device, address, value):
    motor, packet = device
    packet.memory[address] = value
    with pytest.raises(RuntimeError):
        motor.nudge(5)
    assert not packet.writes


@pytest.mark.parametrize("start,delta", [(2, -5), (4090, 5), (32769, 5)])
def test_boundary_failure_cannot_enable_torque(device, start, delta):
    motor, packet = device
    packet.memory[56] = start
    with pytest.raises(ValueError):
        motor.nudge(delta)
    assert (40, 1) not in packet.writes
    assert packet.memory[40] == 0


def test_saved_limits_are_respected(device):
    motor, packet = device
    packet.memory[11] = 2050
    with pytest.raises(ValueError):
        motor.nudge(5)
    assert (40, 1) not in packet.writes


def test_old_goal_cannot_cause_startup_jump(device):
    motor, packet = device
    packet.memory.update({44: 1000, 48: 100})
    result = motor.nudge(5)
    assert packet.positions == [2048, 2048, result["target"]]
    assert packet.memory[44] == 0
    assert packet.memory[48] == 100  # Never increase a pre-existing lower limit.
    assert packet.memory[40] == 0
    assert all(address >= 40 for address, _ in packet.writes)


def test_lost_enable_ack_still_releases_torque(device):
    motor, packet = device
    packet.fail_at = (40, 1)
    with pytest.raises(RuntimeError, match="Communication timeout"):
        motor.nudge(5)
    assert packet.writes[-1] == (40, 0)
    assert packet.memory[40] == 0


def test_interrupt_releases_torque(device, monkeypatch):
    motor, packet = device
    monkeypatch.setattr(motor, "wait", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        motor.nudge(5)
    assert packet.writes[-1] == (40, 0)
    assert packet.memory[40] == 0


def test_unconfirmed_shutdown_is_explicit(device):
    motor, packet = device
    packet.fail_at = (40, 0)
    with pytest.raises(RuntimeError, match="UNCONFIRMED. Disconnect servo power"):
        motor.nudge(5)
    assert (40, 1) not in packet.writes


def test_timeout_releases_torque(device, monkeypatch):
    motor, packet = device
    # Keep normal writes/readbacks, but never report a stopped motor after enabling.
    original = motor.read
    monkeypatch.setattr(motor, "read", lambda address, size=1:
                        1 if address == 66 and packet.memory[40] else original(address, size))
    ticks = iter(range(100))
    monkeypatch.setattr(servo.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(servo.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="Movement timed out"):
        motor.nudge(5)
    assert packet.memory[40] == 0


def test_ram_guard_rejects_persistent_write(device):
    motor, packet = device
    with pytest.raises(ValueError, match="RAM"):
        motor.write(5, 2)
    assert not packet.writes


def test_sdk_serial_exception_does_not_block_torque_off():
    scs = pytest.importorskip("scservo_sdk")
    serial = pytest.importorskip("serial")

    class Wire:
        def __init__(self):
            self.writes = []
            self.reply = b""

        def reset_input_buffer(self):
            self.reply = b""

        def write(self, frame):
            self.writes.append(list(frame))
            if len(self.writes) == 1:
                raise serial.SerialTimeoutException("injected failed move write")
            data = [1, 3, 0, 0] if frame[4] == 2 else [1, 2, 0]
            self.reply = bytes([255, 255, *data, ~sum(data) & 255])
            return len(frame)

        def read(self, length):
            part, self.reply = self.reply[:length], self.reply[length:]
            return part

    port = scs.PortHandler("unused")
    port.ser = Wire()
    port.clearPort = port.ser.reset_input_buffer
    motor = servo.Servo(port, scs.PacketHandler(0), 1)
    with pytest.raises(serial.SerialTimeoutException):
        motor.write(42, 2100, 2)
    assert not port.is_using
    motor.off()
    assert len(port.ser.writes) == 3  # Failed goal, actual torque-off packet, readback.
    assert port.ser.writes[1][4:7] == [3, 40, 0]


def test_sdk_setup_avoids_unbounded_serial_drain(monkeypatch):
    port = SimpleNamespace(is_open=False, ser=Mock(), setBaudRate=Mock(return_value=True))
    port.ser.flush.side_effect = AssertionError("SDK must not drain the serial port")
    packet = Mock()

    def ping(actual_port, _id):
        actual_port.clearPort()
        return 777, 0, 0

    packet.ping.side_effect = ping
    packet.read1ByteTxRx.return_value = (0, 0, 0)
    packet.read2ByteTxRx.return_value = (0, 0, 0)
    sdk = SimpleNamespace(PortHandler=lambda _: port, PacketHandler=lambda _: packet)
    monkeypatch.setitem(sys.modules, "scservo_sdk", sdk)
    # The main entry point imports list_ports even for an explicit device.
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "serial.tools", SimpleNamespace(list_ports=Mock()))
    monkeypatch.setattr(sys, "argv", ["servo.py", "--port", "unused", "status"])
    cli.main()
    assert port.ser.write_timeout == 0.1
    port.ser.reset_input_buffer.assert_called_once()
    port.ser.flush.assert_not_called()


def test_nudge_uses_position_after_torque_release(device, monkeypatch):
    motor, packet = device
    packet.memory.update({40: 1, 42: 2048})
    original = packet.write1ByteTxRx
    def release(port, ident, address, value):
        old = packet.memory[40]
        result = original(port, ident, address, value)
        if address == 40 and old and not value:
            packet.memory[56] -= 10
        return result
    monkeypatch.setattr(packet, "write1ByteTxRx", release)
    result = motor.nudge(5)
    assert result["start"] == 2038 and packet.positions[0] == 2038
    assert packet.memory[40] == 0
