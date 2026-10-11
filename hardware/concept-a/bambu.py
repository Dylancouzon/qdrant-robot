"""Package validated meshes with the saved P1S settings and slice each prototype.
Run with build/hardware-layout/venv/bin/python hardware/concept-a/bambu.py.
"""

from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import subprocess
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "bambu"
BUILD = ROOT.parents[1] / "build" / "hardware-layout" / "bambu"
BINARY = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def clear_preview_metadata(config):
    """Remove cached pick/top maps and point the plate to its current image."""
    keys = {"thumbnail_file", "thumbnail_no_light_file", "top_file", "pick_file"}
    for parent in config.iter():
        for element in list(parent):
            if element.tag == "metadata" and element.get("key") in keys:
                parent.remove(element)
    E.SubElement(
        config.find("plate"), "metadata", key="thumbnail_file", value="Metadata/plate_1.png"
    )
    return config


def current_thumbnail(project, work):
    """Render the current geometry through Bambu's separate PNG action."""
    images = work / "thumbnail"
    images.mkdir(exist_ok=True)
    for name in ("plate_1_0.png", "result.json"):
        (images / name).unlink(missing_ok=True)
    command = [str(BINARY), "--export-png", "0", "--outputdir", str(images), str(project)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (images / "render.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (project.name, result.stdout, result.stderr)
    report = json.loads((images / "result.json").read_text())
    assert report["return_code"] == 0
    png = (images / "plate_1_0.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and len(png) > 100
    with ZipFile(project) as archive:
        data = {n: archive.read(n) for n in archive.namelist() if not n.endswith(".png")}
    config = clear_preview_metadata(E.fromstring(data["Metadata/model_settings.config"]))
    data["Metadata/model_settings.config"] = E.tostring(
        config, encoding="utf-8", xml_declaration=True
    )
    relationships = E.fromstring(data["_rels/.rels"])
    for relationship in relationships:
        if relationship.get("Target", "").endswith(".png"):
            relationship.set("Target", "/Metadata/plate_1.png")
    data["_rels/.rels"] = E.tostring(relationships, encoding="utf-8", xml_declaration=True)
    data["Metadata/plate_1.png"] = png
    with ZipFile(project, "w", ZIP_DEFLATED) as archive:
        for name, content in data.items():
            archive.writestr(name, content)
    return hashlib.sha256(png).hexdigest()


def model_settings(content, source, center, mesh, transform):
    config = E.fromstring(content)
    for element in config.iter("metadata"):
        key = element.get("key")
        if key == "name":
            element.set("value", source.stem)
        elif key == "source_file":
            element.set("value", source.name)
        elif key and key.startswith("source_offset_"):
            element.set("value", str(center["xyz".index(key[-1])]))
        if element.get("face_count") is not None:
            element.set("face_count", str(len(mesh.faces)))
    for element in config.iter("mesh_stat"):
        element.set("face_count", str(len(mesh.faces)))
    for element in config.iter("assemble_item"):
        if element.get("instance_id") is not None:
            element.set("transform", transform)
    return E.tostring(clear_preview_metadata(config), encoding="utf-8", xml_declaration=True)


def package(source, dest):
    """Use native project metadata, retaining exactly the checked input mesh."""
    E.register_namespace("", NS["m"])
    E.register_namespace("p", "http://schemas.microsoft.com/3dmanufacturing/production/2015/06")
    E.register_namespace("BambuStudio", "http://schemas.bambulab.com/package/2021")
    with ZipFile(ROOT / "output" / "power-exit-trial-p1s.3mf") as archive:
        data = {n: archive.read(n) for n in archive.namelist() if not n.endswith(".png")}
    mesh = trimesh.load(source, force="mesh")
    assert mesh.is_watertight and mesh.is_volume
    assert max(mesh.extents[:2]) < 238, "Centered placement must avoid the P1S excluded corner."
    center = mesh.bounds.mean(axis=0)
    model = E.fromstring(data["3D/Objects/object_1.model"])
    element = model.find(".//m:mesh", NS)
    element.clear()
    vertices = E.SubElement(element, "{" + NS["m"] + "}vertices")
    for xyz in mesh.vertices - center:
        E.SubElement(
            vertices,
            "{" + NS["m"] + "}vertex",
            dict(zip(("x", "y", "z"), map(str, xyz), strict=True)),
        )
    faces = E.SubElement(element, "{" + NS["m"] + "}triangles")
    for face in mesh.faces:
        E.SubElement(
            faces,
            "{" + NS["m"] + "}triangle",
            dict(zip(("v1", "v2", "v3"), map(str, face), strict=True)),
        )
    data["3D/Objects/object_1.model"] = E.tostring(model, encoding="utf-8", xml_declaration=True)
    transform = f"1 0 0 0 1 0 0 0 1 128 128 {mesh.extents[2] / 2}"
    model = E.fromstring(data["3D/3dmodel.model"])
    model.find(".//m:build/m:item", NS).set("transform", transform)
    data["3D/3dmodel.model"] = E.tostring(model, encoding="utf-8", xml_declaration=True)
    data["Metadata/model_settings.config"] = model_settings(
        data["Metadata/model_settings.config"], source, center, mesh, transform
    )
    settings = json.loads(data["Metadata/project_settings.config"])
    settings.update(enable_support="1", support_type="tree(auto)", support_on_build_plate_only="0")
    assert settings["printer_model"] == "Bambu Lab P1S"
    assert settings["nozzle_diameter"] == ["0.4"] and settings["layer_height"] == "0.2"
    assert settings["wall_loops"] == "3" and settings["filament_type"] == ["PLA"]
    data["Metadata/project_settings.config"] = json.dumps(settings).encode()
    with ZipFile(dest, "w", ZIP_DEFLATED) as archive:
        for name, content in data.items():
            archive.writestr(name, content)
    return mesh


def main():
    assert BINARY.is_file(), "This workflow needs the installed Bambu Studio macOS application."
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in ("casing", "joint"):
        for source in sorted((ROOT / "output" / group).glob("*.3mf")):
            name = group + "-" + source.stem
            work = BUILD / name
            work.mkdir(parents=True, exist_ok=True)
            template = work / "input.3mf"
            mesh = package(source, template)
            target = name + "-p1s.3mf"
            command = [
                str(BINARY),
                "--slice",
                "0",
                "--outputdir",
                str(work),
                "--export-3mf",
                target,
                str(template),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=180)
            (work / "slice.log").write_text(result.stdout + result.stderr)
            assert result.returncode == 0, (name, result.returncode, result.stderr, result.stdout)
            report = json.loads((work / "result.json").read_text())
            assert report["return_code"] == 0 and len(report["sliced_plates"]) == 1
            plate = report["sliced_plates"][0]
            assert plate["objects"][0]["triangle_count"] == len(mesh.faces)
            bbox = plate["objects"][0]["bbox"]
            assert abs(bbox["z"]) < 0.001
            for axis, dimension in zip(("width", "depth", "height"), mesh.extents, strict=True):
                assert abs(bbox[axis] - dimension) < 0.05
            output = work / target
            assert output.is_file() and (work / "plate_1.gcode").stat().st_size > 100
            thumbnail_hash = current_thumbnail(output, work)
            destination = OUT / target
            destination.write_bytes(output.read_bytes())
            rows.append(
                dict(
                    name=name,
                    source=str(source.relative_to(ROOT)),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    project=target,
                    project_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                    thumbnail_sha256=thumbnail_hash,
                    thumbnail=(
                        "Current geometry rendered by native Bambu CLI; inherited maps removed."
                    ),
                    return_code=report["return_code"],
                    warning=plate.get("warning_message", ""),
                    seconds=plate["total_predication"],
                    grams=plate["filaments"][0]["total_used_g"],
                    layers_height_mm=report["layer_height"],
                    wall_loops=report["wall_loops"],
                    triangles=plate["triangle_count"],
                )
            )
            print(name, "sliced", rows[-1]["warning"] or "without warnings", flush=True)
    (OUT / "slice-checks.json").write_text(
        json.dumps(
            dict(
                printer="Bambu Lab P1S",
                nozzle_mm=0.4,
                material="Bambu PLA Basic",
                layer_mm=0.2,
                walls=3,
                supports="Automatic tree; all surfaces",
                parts=rows,
                status="Slicing passed. Physical fits and support removal require inspection.",
            ),
            indent=2,
        )
        + "\n"
    )
    print(f"{len(rows)} individual P1S projects sliced. No print was sent.")


if __name__ == "__main__":
    main()
