"""Build the pilot scene once: room, bed, lights, cameras and the MPFB person. Saves scene_base.blend.

Needs Blender 4.5 LTS with the MPFB 2.0.18 extension enabled and the MakeHuman
system asset pack (CC0) unpacked in a folder given on the command line:

    blender -b -P build_scene.py -- --assets <folder with clothes/, skins/, eyes/ ...> [--out scene_base.blend]

The saved .blend has every texture packed inside it, so rendering it later
(render_clips.py) needs only Blender: no MPFB and no asset folder.
"""
import argparse
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C          # noqa: E402
import scene_room           # noqa: E402

TEXTURE_MAX = 1024   # the person is under 300 pixels tall in every view; 2048 px textures add nothing


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--assets", required=True)
    p.add_argument("--out", default=os.path.join(HERE, "scene_base.blend"))
    return p.parse_args(argv)


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            coll.remove(item)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def pyjama_material(clothes_obj, assets):
    """Replace the suit's texture colours with plain pale blue, keeping its folds (ambient occlusion and normal map)."""
    name = os.path.basename(C.PERSON_CLOTHES[0])
    folder = os.path.join(assets, "clothes", name)
    mat = bpy.data.materials.new("pyjamas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    ao = nt.nodes.new("ShaderNodeTexImage")
    ao.image = bpy.data.images.load(os.path.join(folder, name + "_ao.png"))
    ao.image.colorspace_settings.name = "Non-Color"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.8
    mix.inputs[6].default_value = (*C.CLOTHES_COLOUR, 1.0)       # A
    nt.links.new(ao.outputs["Color"], mix.inputs[7])               # B
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    nrm_img = nt.nodes.new("ShaderNodeTexImage")
    nrm_img.image = bpy.data.images.load(os.path.join(folder, name + "_normal.png"))
    nrm_img.image.colorspace_settings.name = "Non-Color"
    nrm = nt.nodes.new("ShaderNodeNormalMap")
    nrm.inputs["Strength"].default_value = 0.6
    nt.links.new(nrm_img.outputs["Color"], nrm.inputs["Color"])
    nt.links.new(nrm.outputs["Normal"], bsdf.inputs["Normal"])
    clothes_obj.data.materials.clear()
    clothes_obj.data.materials.append(mat)


def build_person(assets):
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService

    macro = TargetService.get_default_macro_info_dict()
    for k, v in C.PERSON_MACRO.items():
        macro[k] = v
    body = HumanService.create_human(macro_detail_dict=macro)
    rig = HumanService.add_builtin_rig(body, "game_engine")
    HumanService.set_character_skin(os.path.join(assets, "skins", C.PERSON_SKIN, C.PERSON_SKIN + ".mhmat"),
                                    body, skin_type="MAKESKIN")
    parts = [("eyes", os.path.join(assets, "eyes", C.PERSON_EYES, C.PERSON_EYES + ".mhclo"), "Eyes"),
             ("eyebrows", os.path.join(assets, "eyebrows", C.PERSON_EYEBROWS, C.PERSON_EYEBROWS + ".mhclo"), "Eyebrows"),
             ("hair", os.path.join(assets, "hair", C.PERSON_HAIR, C.PERSON_HAIR + ".mhclo"), "Hair")]
    for cname in C.PERSON_CLOTHES:
        parts.append(("clothes", os.path.join(assets, "clothes", cname, cname + ".mhclo"), "Clothes"))
    added = {}
    for key, path, atype in parts:
        ob = HumanService.add_mhclo_asset(path, body, asset_type=atype, subdiv_levels=0, material_type="MAKESKIN")
        added.setdefault(key, []).append(ob)
    pyjama_material(added["clothes"][0], assets)

    person = bpy.data.collections.new("PERSON")
    bpy.context.scene.collection.children.link(person)
    for ob in [rig, body] + [o for lst in added.values() for o in lst]:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        person.objects.link(ob)
    rig.name = "PERSON_RIG"
    body.name = "PERSON_BODY"
    added["clothes"][0].name = "PERSON_CLOTHES"
    return rig, body, added


def shrink_and_pack_images():
    for img in bpy.data.images:
        if img.source != "FILE" or not img.filepath:
            continue
        try:
            w, h = img.size
            if max(w, h) > TEXTURE_MAX:
                img.scale(min(w, TEXTURE_MAX), min(h, TEXTURE_MAX))
            img.pack()
        except Exception as e:  # noqa: BLE001
            print("could not pack", img.name, e)


def main():
    a = args()
    t0 = time.time()
    clear_scene()
    scene = bpy.context.scene
    scene.name = "bedside"
    scene.unit_settings.system = "METRIC"
    scene_room.build_room()
    scene_room.build_lights()
    scene_room.build_cameras()
    scene_room.setup_world()
    rig, body, added = build_person(a.assets)
    # rest the person standing beside the bed until a motion script moves it
    rig.location = (1.2, 2.4, 0.0)
    scene_room.place_cameras(C.CAMERAS["foot_centre_2.2"])
    scene.camera = bpy.data.objects["CAM_COLOUR"]
    shrink_and_pack_images()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out), compress=True)
    print("SAVED", a.out, "in", round(time.time() - t0, 1), "s")
    for ob in bpy.data.collections["PERSON"].objects:
        print("PERSON object", ob.name, ob.type, [m.type for m in getattr(ob, "modifiers", [])])


if __name__ == "__main__":
    main()
