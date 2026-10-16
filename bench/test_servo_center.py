"""Check approved centering writes and uncertain-transaction cleanup without hardware."""
from types import SimpleNamespace

import pytest

from bench import servo_center as setup
from robot.servo import Servo


class Wire:
    def __init__(self):
        self.memory = bytearray(80)
        self.memory[0:2] = bytes([3, 10])
        self.memory[3:5] = (777).to_bytes(2, "little")
        self.memory[5] = 1
        self.memory[11:13] = (4095).to_bytes(2, "little")
        self.memory[55], self.memory[62], self.memory[63] = 1, 54, 34
        self.writes, self.failures = [], set()

    def read1ByteTxRx(self, _port, _id, address):
        return self.memory[address], 0, 0

    def read2ByteTxRx(self, _port, _id, address):
        if address == 56:
            return 4066 - int.from_bytes(self.memory[31:33], "little"), 0, 0
        return int.from_bytes(self.memory[address:address + 2], "little"), 0, 0

    def write(self, address, value, size):
        self.writes.append((address, value, size))
        self.memory[address:address + size] = value.to_bytes(size, "little")
        return (-6, 0) if (address, value) in self.failures else (0, 0)

    def write1ByteTxRx(self, _port, _id, address, value):
        return self.write(address, value, 1)

    def write2ByteTxRx(self, _port, _id, address, value):
        return self.write(address, value, 2)

    @staticmethod
    def getTxRxResult(_result):
        return "Lost acknowledgement"


@pytest.fixture
def device(monkeypatch):
    monkeypatch.setattr(setup.time, "sleep", lambda _: None)
    wire = Wire()
    servo = Servo(SimpleNamespace(is_using=False), wire, 1)
    backup = {"saved_registers_0_39": list(wire.memory[:40]), "goal": 0}
    return servo, wire, backup


def execute(device, tmp_path, operation="apply"):
    servo, _, backup = device
    record = {}
    setup.change(servo, backup, operation, record, tmp_path / "result.json")
    return record


def test_apply_verify_and_rollback(device, tmp_path):
    _, wire, _ = device
    record = execute(device, tmp_path)
    assert record["after"]["status"]["position"] == 2048
    assert wire.writes == [(55, 0, 1), (31, 2018, 2), (55, 1, 1), (40, 0, 1)]
    wire.writes.clear()
    assert execute(device, tmp_path, "verify")["status"] == "passed"
    assert wire.writes == []
    assert execute(device, tmp_path, "rollback")["after"]["status"]["position"] == 4066
    assert wire.writes == [(55, 0, 1), (31, 0, 2), (55, 1, 1), (40, 0, 1)]


@pytest.mark.parametrize("address,value", [(0, 4), (9, 1), (31, 2), (40, 1), (55, 0),
                                            (62, 61), (63, 60), (65, 1), (66, 1), (42, 4)])
def test_changed_or_unsafe_preflight_writes_nothing(device, tmp_path, address, value):
    _, wire, _ = device
    wire.memory[address] = value
    with pytest.raises(RuntimeError):
        execute(device, tmp_path)
    assert wire.writes == []


@pytest.mark.parametrize("failure", [(55, 0), (31, 2018), (55, 1), (40, 0)])
def test_uncertain_write_is_not_retried_and_cleanup_runs(device, tmp_path, failure):
    _, wire, _ = device
    wire.failures.add(failure)
    with pytest.raises(RuntimeError, match="Disconnect servo power"):
        execute(device, tmp_path)
    assert wire.writes.count((*failure, 2 if failure[0] == 31 else 1)) == 1
    assert wire.writes[-2:] == [(55, 1, 1), (40, 0, 1)]
    assert wire.memory[40] == 0


def test_original_and_cleanup_errors_are_preserved(device, tmp_path):
    import json
    _, wire, backup = device
    wire.failures.update({(31, 2018), (55, 1), (40, 0)})
    record = {}
    with pytest.raises(RuntimeError):
        setup.change(device[0], backup, "apply", record, tmp_path / "result.json")
    assert len(record["errors"]) == 3
    # The pre-write intent survives even if the caller cannot save its final error.
    assert json.loads((tmp_path / "result.json").read_text())["write_attempted"]


def test_distinct_primary_and_cleanup_causes_are_preserved(device, tmp_path, monkeypatch):
    servo, _, backup = device
    original = servo._write
    messages = {(31, 2018): "primary failure", (55, 1): "relock failure",
                (40, 0): "release acknowledgement lost"}

    def fail(address, value, size=1):
        original(address, value, size)
        if message := messages.get((address, value)):
            raise RuntimeError(message)

    monkeypatch.setattr(servo, "_write", fail)
    record = {}
    with pytest.raises(RuntimeError):
        setup.change(servo, backup, "apply", record, tmp_path / "result.json")
    assert "primary failure" in record["errors"][0]
    assert "relock failure" in record["errors"][1]
    assert "release acknowledgement lost" in record["errors"][2]
    assert "Torque off is UNCONFIRMED" in record["errors"][2]


@pytest.mark.parametrize("read_number", [1, 21])
def test_delayed_sampling_or_final_status_prevents_unlock(
        device, tmp_path, monkeypatch, read_number):
    servo, wire, _ = device
    original = servo.status
    clock, reads = [0.], [0]
    monkeypatch.setattr(setup.time, "monotonic", lambda: clock[0])

    def delayed():
        reads[0] += 1
        if reads[0] == read_number:
            clock[0] += .31
        return original()

    monkeypatch.setattr(servo, "status", delayed)
    with pytest.raises(RuntimeError, match="read exceeded"):
        execute(device, tmp_path)
    assert wire.writes == []


@pytest.mark.parametrize("address,value", [(5, 2), (31, 1), (40, 1), (42, 2047), (55, 2)])
def test_setup_write_restriction(device, address, value):
    servo, wire, _ = device
    with pytest.raises(ValueError):
        setup.setting(servo, address, value)
    assert wire.writes == []


def test_runtime_still_rejects_offset_and_unlock(device):
    servo, wire, _ = device
    for address, value in ((31, 2018), (55, 0)):
        with pytest.raises(ValueError, match="RAM"):
            servo.write(address, value, 2 if address == 31 else 1)
    assert wire.writes == []


def test_record_failure_prevents_unlock(device, tmp_path, monkeypatch):
    _, wire, _ = device
    monkeypatch.setattr(setup, "save", lambda *_: (_ for _ in ()).throw(OSError("Disk full")))
    with pytest.raises(OSError, match="Disk full"):
        execute(device, tmp_path)
    assert wire.writes == []
