"""Package every print STL as a native P1S project (PLA, 0.4 mm nozzle, 0.2 mm layers, supports
off), slice each with the installed Bambu Studio, and record time and grams per part.
Run with build/hardware-layout/venv/bin/python. It sends nothing to a printer.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZIP_DEFLATED, ZipFile

import trimesh

HERE = Path(__file__).resolve().parent
PRINT, OUT = HERE / "output" / "print", HERE / "output" / "bambu"
BUILD = HERE.parents[1] / "build" / "enclosure-bambu"
TEMPLATE = HERE / "p1s-template.3mf"  # saved P1S settings and one object to replace
BINARY = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
COLOURS = {"Black": "#1A1A1A"}  # every other part prints in white
PREVIEW_KEYS = {"thumbnail_file", "thumbnail_no_light_file", "top_file", "pick_file"}


def run(*args, **kwargs):
    result = subprocess.run(
        [str(BINARY), *map(str, args)], capture_output=True, text=True, **kwargs
    )
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def clear_preview_metadata(config):
    "Drop the template's cached preview images and point the plate at a fresh one."
    for parent in config.iter():
        for element in list(parent):
            if element.tag == "metadata" and element.get("key") in PREVIEW_KEYS:
                parent.remove(element)
    E.SubElement(
        config.find("plate"), "metadata", key="thumbnail_file", value="Metadata/plate_1.png"
    )
    return config


def model_settings(content, stl, center, faces, transform):
    config = E.fromstring(content)
    for element in config.iter("metadata"):
        key = element.get("key")
        if key == "name":
            element.set("value", stl.stem)
        elif key == "source_file":
            element.set("value", stl.name)
        elif key and key.startswith("source_offset_"):
            element.set("value", str(center["xyz".index(key[-1])]))
        if element.get("face_count") is not None:
            element.set("face_count", str(faces))
    for element in config.iter("mesh_stat"):
        element.set("face_count", str(faces))
    for element in config.iter("assemble_item"):
        if element.get("instance_id") is not None:
            element.set("transform", transform)
    return E.tostring(clear_preview_metadata(config), encoding="utf-8", xml_declaration=True)


def package(stl, dest, colour):
    "Write the template project with the STL mesh in place of its object, centred on the plate."
    E.register_namespace("", NS["m"])
    E.register_namespace("p", "http://schemas.microsoft.com/3dmanufacturing/production/2015/06")
    E.register_namespace("BambuStudio", "http://schemas.bambulab.com/package/2021")
    with ZipFile(TEMPLATE) as archive:
        data = {n: archive.read(n) for n in archive.namelist() if not n.endswith(".png")}
    mesh = trimesh.load(stl, force="mesh")
    assert mesh.is_watertight and mesh.is_volume
    assert max(mesh.extents[:2]) < 238, "the P1S bed has an excluded corner"
    center = mesh.bounds.mean(axis=0)
    model = E.fromstring(data["3D/Objects/object_1.model"])
    element = model.find(".//m:mesh", NS)
    element.clear()
    vertices = E.SubElement(element, "{" + NS["m"] + "}vertices")
    for xyz in mesh.vertices - center:
        E.SubElement(
            vertices, "{" + NS["m"] + "}vertex", dict(zip("xyz", map(str, xyz), strict=True))
        )
    triangles = E.SubElement(element, "{" + NS["m"] + "}triangles")
    for face in mesh.faces:
        E.SubElement(
            triangles,
            "{" + NS["m"] + "}triangle",
            dict(zip(("v1", "v2", "v3"), map(str, face), strict=True)),
        )
    data["3D/Objects/object_1.model"] = E.tostring(model, encoding="utf-8", xml_declaration=True)
    transform = f"1 0 0 0 1 0 0 0 1 128 128 {mesh.extents[2] / 2}"
    model = E.fromstring(data["3D/3dmodel.model"])
    model.find(".//m:build/m:item", NS).set("transform", transform)
    data["3D/3dmodel.model"] = E.tostring(model, encoding="utf-8", xml_declaration=True)
    data["Metadata/model_settings.config"] = model_settings(
        data["Metadata/model_settings.config"], stl, center, len(mesh.faces), transform
    )
    settings = json.loads(data["Metadata/project_settings.config"])
    settings.update(enable_support="0", filament_colour=[colour])
    assert settings["printer_model"] == "Bambu Lab P1S" and settings["filament_type"] == ["PLA"]
    assert settings["nozzle_diameter"] == ["0.4"] and settings["layer_height"] == "0.2"
    assert settings["wall_loops"] == "3"
    data["Metadata/project_settings.config"] = json.dumps(settings).encode()
    write(dest, data)
    return mesh


def write(path, data):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, content in data.items():
            archive.writestr(name, content)


def add_thumbnail(project, work):
    "Render the project's current geometry and store it as the cover image."
    run("--export-png", "0", "--outputdir", work, project, timeout=180)
    png = (work / "plate_1_0.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
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
    E.register_namespace("", "http://schemas.openxmlformats.org/package/2006/relationships")
    data["_rels/.rels"] = E.tostring(relationships, encoding="utf-8", xml_declaration=True)
    data["Metadata/plate_1.png"] = png
    write(project, data)
    info = run("--info", project, timeout=180, cwd=work).stdout
    assert re.search(r"number_of_facets\s*[:=]\s*[1-9][0-9]*\b", info), (project.name, info)


def slice_part(stl):
    "Package, slice and check one STL. Return its result row; the project goes under OUT."
    rel = stl.relative_to(PRINT)
    work = BUILD / rel.with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    colour = COLOURS.get(rel.parts[-2], "#FFFFFF")
    mesh = package(stl, work / "input.3mf", colour)
    run(
        "--slice",
        "0",
        "--outputdir",
        work,
        "--export-3mf",
        "sliced.3mf",
        work / "input.3mf",
        timeout=300,
    )
    report = json.loads((work / "result.json").read_text())
    assert report["return_code"] == 0 and len(report["sliced_plates"]) == 1, report
    plate = report["sliced_plates"][0]
    box = plate["objects"][0]["bbox"]
    assert abs(box["z"]) < 0.001 and plate["objects"][0]["triangle_count"] == len(mesh.faces)
    for axis, size in zip(("width", "depth", "height"), mesh.extents, strict=True):
        assert abs(box[axis] - size) < 0.05, (stl.name, axis)
    assert (work / "plate_1.gcode").stat().st_size > 100
    assert not plate.get("warning_message"), (stl.name, plate["warning_message"])
    add_thumbnail(work / "sliced.3mf", work)
    dest = OUT / rel.with_suffix(".3mf")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((work / "sliced.3mf").read_bytes())
    return dict(
        part=str(rel.with_suffix("")),
        project=str(dest.relative_to(HERE)),
        sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
        seconds=plate["total_predication"],
        grams=plate["filaments"][0]["total_used_g"],
        size_mm=[round(float(v), 1) for v in mesh.extents],
    )


def main():
    assert BINARY.is_file(), "This workflow needs the installed Bambu Studio macOS application."
    BUILD.mkdir(parents=True, exist_ok=True)
    rows = []
    for stl in sorted(PRINT.rglob("*.stl")):
        rows.append(slice_part(stl))
        r = rows[-1]
        minutes = r["seconds"] / 60
        print(f"{r['part']:28} {minutes:4.0f} min {r['grams']:6.1f} g")
    settings = "Bambu Lab P1S, 0.4 mm nozzle, Bambu PLA Basic, 0.2 mm layers, 3 walls, supports off"
    (OUT / "slice-checks.json").write_text(
        json.dumps(dict(settings=settings, parts=rows), indent=2)
    )
    print(f"{len(rows)} projects sliced. No print was sent.")


if __name__ == "__main__":
    main()
