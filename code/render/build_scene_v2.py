"""Build scene_v2.blend for clips R23 to R40: scene_base.blend unchanged, plus body B and a chair.

    blender -b scene_base.blend -P build_scene_v2.py -- --assets <system asset pack folder> --dress <Dress 01 pack folder>

Body A, the room, the lights and the cameras are taken as they are from
scene_base.blend (which this script does not overwrite). Body B is made with
MPFB from CC0 assets: an older woman of heavier build in a pale gown (the
"toigo_shift_dress" from the CC0 Dress 01 pack, recoloured). The chair is hidden
in renders unless a motion needs it (L9).
"""
import argparse
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C          # noqa: E402
import scene_room           # noqa: E402
from build_scene import shrink_and_pack_images   # noqa: E402


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--assets", required=True)
    p.add_argument("--dress", required=True)
    p.add_argument("--out", default=os.path.join(HERE, "scene_v2.blend"))
    return p.parse_args(argv)


def gown_material(ob, folder, name):
    """Plain pale gown: one colour, the dress's own texture used only as faint shading."""
    mat = bpy.data.materials.new("gown")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(folder, "ShiftDress.png"))
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(tex.outputs["Color"], bw.inputs["Color"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    r, g, b = C.PERSON_B_CLOTHES_COLOUR
    ramp.color_ramp.elements[0].color = (r * 0.85, g * 0.85, b * 0.85, 1.0)
    ramp.color_ramp.elements[1].color = (r, g, b, 1.0)
    nt.links.new(bw.outputs["Val"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def build_body_b(assets, dress_root):
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService

    macro = TargetService.get_default_macro_info_dict()
    for k, v in C.PERSON_B_MACRO.items():
        macro[k] = v
    body = HumanService.create_human(macro_detail_dict=macro)
    rig = HumanService.add_builtin_rig(body, "game_engine")
    HumanService.set_character_skin(os.path.join(assets, "skins", C.PERSON_B_SKIN, C.PERSON_B_SKIN + ".mhmat"),
                                    body, skin_type="MAKESKIN")
    eyes = HumanService.add_mhclo_asset(os.path.join(assets, "eyes", "low-poly", "low-poly.mhclo"), body,
                                        asset_type="Eyes", subdiv_levels=0, material_type="MAKESKIN")
    brows = HumanService.add_mhclo_asset(os.path.join(assets, "eyebrows", C.PERSON_B_EYEBROWS, C.PERSON_B_EYEBROWS + ".mhclo"),
                                         body, asset_type="Eyebrows", subdiv_levels=0, material_type="MAKESKIN")
    hair = HumanService.add_mhclo_asset(os.path.join(assets, "hair", C.PERSON_B_HAIR, C.PERSON_B_HAIR + ".mhclo"), body,
                                        asset_type="Hair", subdiv_levels=0, material_type="MAKESKIN")
    folder = os.path.join(dress_root, "clothes", C.PERSON_B_CLOTHES)
    dress = HumanService.add_mhclo_asset(os.path.join(folder, C.PERSON_B_CLOTHES + ".mhclo"), body,
                                         asset_type="Clothes", subdiv_levels=0, material_type="MAKESKIN")
    gown_material(dress, folder, C.PERSON_B_CLOTHES)
    col = bpy.data.collections.new("PERSON_B")
    bpy.context.scene.collection.children.link(col)
    for ob in (rig, body, eyes, brows, hair, dress):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        col.objects.link(ob)
    rig.name, body.name, eyes.name, brows.name, hair.name, dress.name = (
        "PERSON_B_RIG", "PERSON_B_BODY", "PERSON_B_EYES", "PERSON_B_EYEBROWS", "PERSON_B_HAIR", "PERSON_B_CLOTHES")
    rig.location = (2.6, 0.8, 0.0)     # parked in a corner until a motion moves it
    return rig, body


def main():
    a = args()
    if os.path.abspath(a.out) == os.path.abspath(os.path.join(HERE, "scene_base.blend")):
        raise SystemExit("refusing to overwrite scene_base.blend")
    rig, body = build_body_b(a.assets, a.dress)
    scene_room.build_chair()
    bpy.data.collections["CHAIR"].hide_render = True
    shrink_and_pack_images()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out), compress=True)
    print("SAVED", a.out, "body B height", round(body.dimensions.z, 3))


if __name__ == "__main__":
    main()
