"""Lay every print STL out on plates of three native P1S projects, one per colour (PLA, 0.4 mm
nozzle, 0.2 mm layers, supports off), slice each plate with the installed Bambu Studio, and record
time and grams per plate. Run with build/hardware-layout/venv/bin/python. It sends nothing to a
printer.
"""

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZIP_DEFLATED, ZipFile

import trimesh

HERE = Path(__file__).resolve().parent
PRINT, OUT = HERE / "output" / "print", HERE / "output" / "bambu"
BUILD = HERE.parents[1] / "build" / "enclosure-bambu"
TEMPLATE = HERE / "p1s-template.3mf"  # saved P1S settings, content types and slice info
BINARY = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
BED, GAP, EDGE = 256, 10, 10  # P1S bed, minimum part spacing, minimum distance to a bed edge
EXCLUDED = (18, 28)  # the P1S bed excludes this front-left corner
PLATE_STRIDE = BED * 1.2  # Bambu Studio lays plates out on a grid with a 20% gap
# Per project: filament colour, then its plates. A plate has a name and rows of parts; rows stack
# front to back, and the parts of a row sit side by side.
PROJECTS = {
    "Test pieces/Test pieces": (
        "#FFFFFF",
        [
            (
                "Test pieces: fit plate and Jetson slot",
                [["Test pieces/fit-test-plate", "Test pieces/slot-test-piece"]],
            )
        ],
    ),
    "White": (
        "#FFFFFF",
        [
            (
                "White 1: body shell and port panel",
                [["Required/White/body-shell"], ["Required/White/port-panel"]],
            ),
            (
                "White 2: base plate and head shell",
                [["Required/White/base-plate"], ["Required/White/head-shell"]],
            ),
        ],
    ),
    "Black": (
        "#1A1A1A",
        [
            (
                "Black: visor, speaker grille, neck hub, head shaft and horn disc",
                [
                    ["Required/Black/visor", "Required/Black/speaker-grille"],
                    [
                        "Required/Black/neck-hub",
                        "Required/Black/head-shaft",
                        "Required/Black/horn-disc",
                    ],
                ],
            )
        ],
    ),
}
ROOT = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
COVER = "http://schemas.bambulab.com/package/2021/cover-thumbnail"
MODEL_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
    'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
    'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
    'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
    'requiredextensions="p">\n <metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
    ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
)


def run(*args, **kwargs):
    result = subprocess.run(
        [str(BINARY), *map(str, args)], capture_output=True, text=True, **kwargs
    )
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def write(path, data):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, content in data.items():
            archive.writestr(name, content)


def read_without_images(path):
    with ZipFile(path) as archive:
        return {n: archive.read(n) for n in archive.namelist() if not n.endswith(".png")}


def xml(element):
    E.indent(element)
    return E.tostring(element, encoding="utf-8", xml_declaration=True)


def centres(rows):
    "Place meshes (a list of rows) on the bed, GAP apart, centred. Return each mesh's centre."
    heights = [max(m.extents[1] for m in row) for row in rows]
    y = (BED - sum(heights) - GAP * (len(rows) - 1)) / 2
    result = []
    for row, height in zip(rows, heights, strict=True):
        x = (BED - sum(m.extents[0] for m in row) - GAP * (len(row) - 1)) / 2
        for mesh in row:
            centre = (x + mesh.extents[0] / 2, y + height / 2)
            low, front = centre[0] - mesh.extents[0] / 2, centre[1] - mesh.extents[1] / 2
            assert min(low, front) >= EDGE, "part too close to the bed edge"
            assert centre[0] + mesh.extents[0] / 2 <= BED - EDGE, "part too close to the bed edge"
            assert centre[1] + mesh.extents[1] / 2 <= BED - EDGE, "part too close to the bed edge"
            assert low >= EXCLUDED[0] + EDGE or front >= EXCLUDED[1] + EDGE, (
                "part in the bed corner"
            )
            result.append(centre)
            x += mesh.extents[0] + GAP
        y += height + GAP
    return result


def object_files(index, mesh, centre):
    "The object's mesh file (centred on its own origin) and its entry in 3dmodel.model."
    vertices = "".join(
        f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in mesh.vertices - mesh.bounds.mean(axis=0)
    )
    triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces)
    inner = 2 * index - 1
    body = (
        f'{MODEL_HEAD} <resources>\n  <object id="{inner}" '
        f'p:UUID="{index:04x}0000-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n'
        f"    <vertices>{vertices}</vertices>\n    <triangles>{triangles}</triangles>\n"
        "   </mesh>\n  </object>\n </resources>\n <build/>\n</model>"
    )
    obj = (
        f'  <object id="{2 * index}" type="model" '
        f'p:UUID="{index:08x}-61cb-4c03-9d28-80fed5dfa1dc">\n'
        f'   <components>\n    <component p:path="/3D/Objects/object_{index}.model" '
        f'objectid="{inner}" p:UUID="{index:04x}0000-b206-40ff-9872-83e8017abed1" '
        'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n   </components>\n  </object>\n'
    )
    return body.encode(), obj


def package(colour, plates, dest):
    "Write one project: every plate's parts, stacked on the bed. Return the meshes per plate."
    data = read_without_images(TEMPLATE)
    objects, items, config, assemble, rels, meshes_per_plate = (
        "",
        "",
        E.Element("config"),
        "",
        "",
        [],
    )
    index = 0
    plate_elements = []
    for plate_number, (name, rows) in enumerate(plates):
        stems = [stem for row in rows for stem in row]
        meshes = [trimesh.load(PRINT / f"{s}.stl", force="mesh") for s in stems]
        for mesh, stem in zip(meshes, stems, strict=True):
            assert mesh.is_watertight and mesh.is_volume, stem
        meshes_per_plate.append(meshes)
        plate = E.Element("plate")
        for key, value in (
            ("plater_id", plate_number + 1),
            ("plater_name", name),
            ("locked", "false"),
            ("filament_map_mode", "Auto For Flush"),
            ("filament_maps", 1),
            ("filament_volume_maps", 0),
        ):
            E.SubElement(plate, "metadata", key=key, value=str(value))
        column = plate_number % math.ceil(math.sqrt(len(plates)))
        row = plate_number // math.ceil(math.sqrt(len(plates)))
        shape = [len(row) for row in rows]
        grouped = [meshes[sum(shape[:i]) : sum(shape[: i + 1])] for i in range(len(rows))]
        for stem, mesh, (x, y) in zip(stems, meshes, centres(grouped), strict=True):
            index += 1
            mesh_file, obj = object_files(index, mesh, (x, y))
            data[f"3D/Objects/object_{index}.model"] = mesh_file
            objects += obj
            z = mesh.extents[2] / 2
            moved = f"1 0 0 0 1 0 0 0 1 {x + column * PLATE_STRIDE} {y - row * PLATE_STRIDE} {z}"
            items += (
                f'  <item objectid="{2 * index}" p:UUID="{index:08x}-b1ec-4553-aec9-835e5b724bb4" '
                f'transform="{moved}" printable="1"/>\n'
            )
            rels += (
                f' <Relationship Target="/3D/Objects/object_{index}.model" Id="rel-{index}" '
                f'Type="{RELATIONSHIP}"/>\n'
            )
            stl, centre, faces = Path(stem).name, mesh.bounds.mean(axis=0), len(mesh.faces)
            obj_config = E.SubElement(config, "object", id=str(2 * index))
            E.SubElement(obj_config, "metadata", key="name", value=stl)
            E.SubElement(obj_config, "metadata", key="extruder", value="1")
            E.SubElement(obj_config, "metadata", face_count=str(faces))
            part = E.SubElement(
                obj_config, "part", id=str(2 * index - 1), subtype="normal_part",
                uuid="b73f212f-a706-42cb-aea6-a7a383616495",
            )  # fmt: skip
            for key, value in (
                ("name", stl),
                ("matrix", "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"),
                ("source_file", f"{stl}.stl"),
                ("source_object_id", 0),
                ("source_volume_id", 0),
                *((f"source_offset_{a}", centre["xyz".index(a)]) for a in "xyz"),
            ):
                E.SubElement(part, "metadata", key=key, value=str(value))
            E.SubElement(
                part, "mesh_stat", face_count=str(faces), edges_fixed="0", degenerate_facets="0",
                facets_removed="0", facets_reversed="0", backwards_edges="0",
            )  # fmt: skip
            instance = E.SubElement(plate, "model_instance")
            for key, value in (
                ("object_id", 2 * index), ("instance_id", 0), ("identify_id", 100 + index)
            ):  # fmt: skip
                E.SubElement(instance, "metadata", key=key, value=str(value))
            assemble += (
                f'   <assemble_item object_id="{2 * index}" instance_id="0" '
                f'transform="1 0 0 0 1 0 0 0 1 128 128 {z}" offset="0 0 0" />\n'
                f'   <assemble_item object_id="{2 * index}" volume_id="0" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n'
            )
        plate_elements.append(plate)
    config.extend(plate_elements)
    config.append(E.fromstring(f"<assemble>\n{assemble}  </assemble>"))
    data["Metadata/model_settings.config"] = xml(config)
    data["3D/3dmodel.model"] = (
        f"{MODEL_HEAD} <resources>\n{objects} </resources>\n"
        f' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n{items} </build>\n</model>'
    ).encode()
    data["3D/_rels/3dmodel.model.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="{ROOT}">\n'
        f"{rels}</Relationships>"
    ).encode()
    data["Metadata/cut_information.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n<objects>\n'
        + "".join(
            f' <object id="{i}">\n  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n </object>\n'
            for i in range(1, index + 1)
        )
        + "</objects>"
    ).encode()
    data["Metadata/filament_sequence.json"] = json.dumps(
        {
            f"plate_{n + 1}": dict(nozzle_sequence=[], optimal_assignment=[], sequence=[])
            for n in range(len(plates))
        }
    ).encode()
    data["_rels/.rels"] = write_covers()
    settings = json.loads(data["Metadata/project_settings.config"])
    settings.update(enable_support="0", filament_colour=[colour])
    assert settings["printer_model"] == "Bambu Lab P1S" and settings["filament_type"] == ["PLA"]
    assert settings["nozzle_diameter"] == ["0.4"] and settings["layer_height"] == "0.2"
    assert settings["wall_loops"] == "3"
    data["Metadata/project_settings.config"] = json.dumps(settings).encode()
    write(dest, data)
    return meshes_per_plate


def write_covers():
    "Package relationships, with the first plate's picture as the project cover."
    cover = "/Metadata/plate_1.png"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="{ROOT}">\n'
        f' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="{RELATIONSHIP}"/>\n'
        f' <Relationship Target="{cover}" Id="rel-2" Type="{ROOT}/metadata/thumbnail"/>\n'
        f' <Relationship Target="{cover}" Id="rel-4" Type="{COVER}-middle"/>\n'
        f' <Relationship Target="{cover}" Id="rel-5" Type="{COVER}-small"/>\n'
        "</Relationships>"
    ).encode()


def add_thumbnails(project, work, plates):
    "Render every plate and store it as that plate's picture; restore the plate names."
    run("--export-png", "0", "--outputdir", work, project, timeout=180 * len(plates))
    data = read_without_images(project)
    config = E.fromstring(data["Metadata/model_settings.config"])
    elements = list(config.iter("plate"))
    assert len(elements) == len(plates), (project.name, len(elements))
    for number, (element, (name, _)) in enumerate(zip(elements, plates, strict=True), 1):
        png = (work / f"plate_{number}_0.png").read_bytes()
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        data[f"Metadata/plate_{number}.png"] = png
        for meta in element.findall("metadata"):  # their images are dropped
            if meta.get("key") in {"thumbnail_no_light_file", "top_file", "pick_file"}:
                element.remove(meta)
            elif meta.get("key") == "thumbnail_file":
                meta.set("value", f"Metadata/plate_{number}.png")
            elif meta.get("key") == "plater_name":
                meta.set("value", name)
    data["Metadata/model_settings.config"] = xml(config)
    write(project, data)
    info = run("--info", project, timeout=180, cwd=work).stdout
    assert info.count("number_of_facets") >= len(plates), (project.name, info)


def slice_project(name, out):
    "Package, slice and check one project. Return one result row per plate."
    colour, plates = PROJECTS[name]
    work = BUILD / name
    work.mkdir(parents=True, exist_ok=True)
    meshes_per_plate = package(colour, plates, work / "input.3mf")
    run(
        "--slice", "0", "--outputdir", work, "--export-3mf", "sliced.3mf", work / "input.3mf",
        timeout=300 * len(plates),
    )  # fmt: skip
    report = json.loads((work / "result.json").read_text())
    assert report["return_code"] == 0 and len(report["sliced_plates"]) == len(plates), report
    add_thumbnails(work / "sliced.3mf", work, plates)
    dest = out / f"{name}.3mf"
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes((work / "sliced.3mf").read_bytes())
    results = []
    for number, ((plate_name, rows), meshes, plate) in enumerate(
        zip(plates, meshes_per_plate, report["sliced_plates"], strict=True), 1
    ):
        stems = [stem for row in rows for stem in row]
        assert (work / f"plate_{number}.gcode").stat().st_size > 100
        assert not plate.get("warning_message"), (plate_name, plate["warning_message"])
        assert len(plate["objects"]) == len(stems), (plate_name, plate["objects"])
        by_faces = sorted(plate["objects"], key=lambda o: o["triangle_count"])
        for obj, mesh in zip(by_faces, sorted(meshes, key=lambda m: len(m.faces)), strict=True):
            box = obj["bbox"]
            assert abs(box["z"]) < 0.001 and obj["triangle_count"] == len(mesh.faces), plate_name
            for axis, size in zip(("width", "depth", "height"), mesh.extents, strict=True):
                assert abs(box[axis] - size) < 0.05, (plate_name, axis)
        results.append(
            dict(
                project=str(OUT.relative_to(HERE) / f"{name}.3mf"),
                plate=number,
                name=plate_name,
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                seconds=plate["total_predication"],
                grams=plate["filaments"][0]["total_used_g"],
                parts={
                    Path(s).name: [round(float(v), 1) for v in m.extents]
                    for s, m in zip(stems, meshes, strict=True)
                },
            )
        )
    return results


def main():
    assert BINARY.is_file(), "This workflow needs the installed Bambu Studio macOS application."
    BUILD.mkdir(parents=True, exist_ok=True)
    staging = BUILD / "out"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    rows = []
    for name in PROJECTS:
        for r in slice_project(name, staging):
            rows.append(r)
            print(f"{r['name']:48} {r['seconds'] / 60:4.0f} min {r['grams']:6.1f} g")
    settings = "Bambu Lab P1S, 0.4 mm nozzle, Bambu PLA Basic, 0.2 mm layers, 3 walls, supports off"
    (staging / "slice-checks.json").write_text(
        json.dumps(dict(settings=settings, plates=rows), indent=2)
    )
    shutil.rmtree(OUT, ignore_errors=True)  # replaced only after every plate succeeded
    shutil.move(staging, OUT)
    print(f"{len(PROJECTS)} projects, {len(rows)} plates sliced. No print was sent.")


if __name__ == "__main__":
    main()
