"""MELOJI enclosure: a round, Tamagotchi-style case built for 3D printing.

Run headless (writes STLs to cad/stl, previews to cad/renders):
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P cad/meloji_enclosure.py -- --render
or paste into Blender's Scripting tab, or send it through Blender MCP.

Units are millimetres. Axes: X = width (+X is the device's right when you face the screen),
Y = depth (front face at -Y, back face at +Y), Z = height.
Every size below is a parameter: measure your actual parts and adjust before printing.
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------- body ----------
W, H, D = 70.0, 80.0, 30.0      # outer width (X), height (Z), depth (Y)
WALL = 2.0
ROUND = 7.0                     # outer edge radius around the front and back faces
SEAM_Y = -6.0                   # front shell is Y < SEAM_Y, back shell is Y > SEAM_Y
SEG = 128                       # outline smoothness
CLEAR = 0.2                     # gap between a button cap and its hole, per side
FLANGE = 0.8                    # how far a cap's retaining flange reaches past its hole

# ---------- front: screen + 3 buttons ----------
SCREEN = (28.5, 28.5, 8.0)      # window width, height, centre Z (1.54" 240x240 IPS: ~27.7 mm active area)
BTN_Z, BTN_PITCH = -19.0, 14.0  # button row height and spacing
CIRCLE_R = 4.0                  # left: AI-assist button
CROSS_L, CROSS_W = 14.0, 5.0    # middle: D-pad
SQUARE = 7.0                    # right: record button

# ---------- sides ----------
POWER, POWER_Z = 8.0, 12.0      # left side, top: square power button
VOL_R, VOLUP_Z, VOLDN_Z = 3.0, -1.0, -11.0
SLOT_LEN, SLOT_W = 18.5, 2.6    # right side: slot for a 15 mm-travel slide potentiometer

# ---------- bottom ----------
USB_W, USB_H = 12.5, 7.0        # USB-C opening (clears a typical cable overmould)
LUG_ANGLE, LUG_R, LUG_HOLE_R = 225.0, 5.5, 2.0   # lanyard lug, bottom-left

# ---------- back: pop-it rings (ring radius, bubble count, hole radius) ----------
POP = [(0.0, 1, 3.5), (8.5, 6, 3.0), (15.5, 12, 3.0), (22.5, 18, 3.0)]
POP_WALL = 0.6                  # TPU dome thickness
POP_BASE_R, POP_BASE_T = 27.0, 1.0

# ---------- screws (M2 x 12 self-tapping, driven from the back) ----------
BOSSES = [(-20.0, 25.0), (20.0, 25.0), (-22.0, -23.0), (22.0, -23.0)]   # clear a 31.5 x 33.7 mm display panel and the cap flanges
BOSS_R, PILOT_R, CLEAR_R, HEAD_R = 3.2, 0.9, 1.2, 2.3

RX, RZ, HD = W / 2, H / 2, D / 2
IRX, IRZ, IHD = RX - WALL, RZ - WALL, HD - WALL
CAP_TOP = 1.0 + WALL + 1.2      # flange + wall + 1.2 mm standing proud


# ---------- mesh helpers ----------
def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def apply_mods(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = bpy.data.meshes.new_from_object(ev)
    ob.modifiers.clear()
    old, ob.data = ob.data, me
    bpy.data.meshes.remove(old)


def boolean(target, operands, op):
    coll = bpy.data.collections.new("operands")
    bpy.context.scene.collection.children.link(coll)
    for o in operands:
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation, m.solver = op, "EXACT"
    m.operand_type, m.collection = "COLLECTION", coll
    started = time.time()
    apply_mods(target)
    print(f"  {op.lower():10s} {target.name:18s} x{len(operands):<3d} {time.time() - started:6.1f}s", flush=True)
    for o in operands:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)
    return target


def copy(ob, name):
    dup = ob.copy()
    dup.data = ob.data.copy()
    dup.name = name
    bpy.context.scene.collection.objects.link(dup)
    return dup


def prism(name, rx, rz, y0, y1, round_=0.0):
    """Elliptical slab along Y; round_ rounds the edges of its two flat faces."""
    bm = bmesh.new()
    angles = [2 * math.pi * i / SEG for i in range(SEG)]
    a = [bm.verts.new((rx * math.cos(t), y0, rz * math.sin(t))) for t in angles]
    b = [bm.verts.new((rx * math.cos(t), y1, rz * math.sin(t))) for t in angles]
    for i in range(SEG):
        j = (i + 1) % SEG
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a)
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = new_obj(name, bm)
    if round_:
        m = ob.modifiers.new("round", "BEVEL")
        m.width, m.segments = round_, 8
        m.limit_method, m.angle_limit = "ANGLE", math.radians(30)
        m.use_clamp_overlap = False
        apply_mods(ob)
    return ob


def cyl(name, r, h, axis="Z", at=(0, 0, 0), seg=40):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=h)
    rot = {"X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X"), "Z": Matrix.Identity(4)}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(at) @ rot, verts=bm.verts)
    return new_obj(name, bm)


def box(name, x, y, z):
    """Axis-aligned box from (min, max) ranges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    scale = Matrix.Diagonal((x[1] - x[0], y[1] - y[0], z[1] - z[0], 1.0))
    move = Matrix.Translation(((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2))
    bmesh.ops.transform(bm, matrix=move @ scale, verts=bm.verts)
    return new_obj(name, bm)


def sphere(name, r, at):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
    bmesh.ops.translate(bm, vec=Vector(at), verts=bm.verts)
    return new_obj(name, bm)


def pop_layout():
    out = []
    for ring_r, count, hole_r in POP:
        for k in range(count):
            a = math.pi / 2 + 0.001 + 2 * math.pi * k / count   # 0.001 rad keeps hole vertices off the outline's
            out.append((ring_r * math.cos(a), ring_r * math.sin(a), hole_r))
    return out


def cross(name, arm_l, arm_w, z0, z1):
    h = box(name, (-arm_l / 2, arm_l / 2), (-arm_w / 2, arm_w / 2), (z0, z1))
    v = box(name + "_v", (-arm_w / 2, arm_w / 2), (-arm_l / 2, arm_l / 2), (z0, z1))
    return boolean(h, [v], "UNION")


def inner_x(z):
    return IRX * math.sqrt(max(0.0, 1 - (z / IRZ) ** 2))


# ---------- shells ----------
def build_shells():
    shell = boolean(prism("outer", RX, RZ, -HD, HD, ROUND),
                    [prism("inner", IRX, IRZ, -IHD, IHD, ROUND - WALL)], "DIFFERENCE")

    t = math.radians(LUG_ANGLE)
    normal = Vector((math.cos(t) / RX, math.sin(t) / RZ)).normalized()
    lug = Vector((RX * math.cos(t), RZ * math.sin(t))) + normal * 4.0
    adds = [cyl("lug", LUG_R, 6.0, "Y", (lug.x, 0, lug.y))]
    # bosses stop 1 mm into the walls so they never poke through the rounded rim
    bosses = [cyl(f"boss{i}", BOSS_R, 2 * IHD + 1, "Y", (x, 0, z)) for i, (x, z) in enumerate(BOSSES)]
    boss = boolean(bosses[0], bosses[1:], "UNION")
    adds.append(boolean(boss, [prism("boss_limit", IRX + 1, IRZ + 1, -IHD - 1, IHD + 1, ROUND - WALL + 1)], "INTERSECT"))
    boolean(shell, adds, "UNION")

    fy = (-HD - 1, -IHD + 1)                     # through the front wall
    fmid = sum(fy) / 2
    sx, sh, sz = SCREEN
    cuts = [
        box("screen", (-sx / 2, sx / 2), fy, (sz - sh / 2, sz + sh / 2)),
        cyl("btn_circle", CIRCLE_R, 4, "Y", (-BTN_PITCH, fmid, BTN_Z)),
        box("btn_cross_h", (-CROSS_L / 2, CROSS_L / 2), fy, (BTN_Z - CROSS_W / 2, BTN_Z + CROSS_W / 2)),
        box("btn_cross_v", (-CROSS_W / 2, CROSS_W / 2), fy, (BTN_Z - CROSS_L / 2, BTN_Z + CROSS_L / 2)),
        box("btn_square", (BTN_PITCH - SQUARE / 2, BTN_PITCH + SQUARE / 2), fy, (BTN_Z - SQUARE / 2, BTN_Z + SQUARE / 2)),
        box("power", (-RX - 2, -IRX + 4), (-POWER / 2, POWER / 2), (POWER_Z - POWER / 2, POWER_Z + POWER / 2)),
        cyl("vol_up", VOL_R, 8, "X", (-RX + 1, 0, VOLUP_Z)),
        cyl("vol_down", VOL_R, 8, "X", (-RX + 1, 0, VOLDN_Z)),
        box("slider", (IRX - 4, RX + 2), (-SLOT_W / 2, SLOT_W / 2), (-SLOT_LEN / 2, SLOT_LEN / 2)),
        box("usb_c", (-USB_W / 2, USB_W / 2), (-USB_H / 2, USB_H / 2), (-RZ - 3, -IRZ + 2)),
        cyl("lug_hole", LUG_HOLE_R, 10, "Y", (lug.x, 0, lug.y)),
    ]
    cuts += [cyl(f"pop{i}", r, 4, "Y", (x, IHD + 1, z)) for i, (x, z, r) in enumerate(pop_layout())]
    cuts += [cyl(f"pilot{i}", PILOT_R, HD + IHD - 1, "Y", (x, (HD - IHD + 1) / 2, z)) for i, (x, z) in enumerate(BOSSES)]
    boolean(shell, cuts, "DIFFERENCE")

    front = boolean(copy(shell, "front_shell"), [box("keep_front", (-60, 60), (-30, SEAM_Y), (-60, 60))], "INTERSECT")
    back = boolean(shell, [box("keep_back", (-60, 60), (SEAM_Y, 30), (-60, 60))], "INTERSECT")
    back.name = "back_shell"

    # screw clearance + head counterbore through the back half
    screw = []
    for i, (x, z) in enumerate(BOSSES):
        screw.append(cyl(f"clear{i}", CLEAR_R, HD - SEAM_Y + 2, "Y", (x, (HD + SEAM_Y) / 2, z)))
        screw.append(cyl(f"head{i}", HEAD_R, HD + 1, "Y", (x, (HD + 1) / 2, z)))
    boolean(back, screw, "DIFFERENCE")

    # alignment lip on the back shell that slides 2.5 mm inside the front shell
    lip = boolean(prism("lip", IRX - 0.25, IRZ - 0.25, SEAM_Y - 2.5, SEAM_Y + 0.5),
                  [prism("bridge", IRX + 1.0, IRZ + 1.0, SEAM_Y + 0.3, SEAM_Y + 1.3)], "UNION")
    hollow = [prism("lip_in", IRX - 1.45, IRZ - 1.45, SEAM_Y - 3, SEAM_Y + 1.5)]
    hollow += [cyl(f"lip_boss{i}", BOSS_R + 0.4, 6, "Y", (x, SEAM_Y - 1.5, z)) for i, (x, z) in enumerate(BOSSES)]
    boolean(lip, hollow, "DIFFERENCE")
    boolean(back, [lip], "UNION")
    return front, back


# ---------- caps and inserts, modelled in print orientation (flange on the bed, z up) ----------
def round_cap(name, hole_r):
    cap = cyl(name, hole_r + FLANGE, 1.0, at=(0, 0, 0.5))
    stem = cyl(name + "_stem", hole_r - CLEAR, CAP_TOP - 1.0, at=(0, 0, (1.0 + CAP_TOP) / 2))
    return boolean(cap, [stem], "UNION")


def square_cap(name, side):
    f, s = side / 2 + FLANGE, side / 2 - CLEAR
    cap = box(name, (-f, f), (-f, f), (0, 1.0))
    return boolean(cap, [box(name + "_stem", (-s, s), (-s, s), (1.0, CAP_TOP))], "UNION")


def build_caps():
    parts = {
        "cap_ai_circle": round_cap("cap_ai_circle", CIRCLE_R),
        "cap_record_square": square_cap("cap_record_square", SQUARE),
        "cap_power": square_cap("cap_power", POWER),
    }
    dpad = cross("cap_dpad", CROSS_L + 2 * FLANGE, CROSS_W + 2 * FLANGE, 0, 1.0)
    parts["cap_dpad"] = boolean(dpad, [cross("dpad_stem", CROSS_L - 2 * CLEAR, CROSS_W - 2 * CLEAR, 1.0, CAP_TOP)], "UNION")

    up = round_cap("cap_vol_up", VOL_R)
    parts["cap_vol_up"] = boolean(up, [cross("plus", 3.2, 0.8, CAP_TOP - 0.1, CAP_TOP + 0.5)], "UNION")
    down = round_cap("cap_vol_down", VOL_R)
    parts["cap_vol_down"] = boolean(down, [box("minus", (-0.4, 0.4), (-1.6, 1.6), (CAP_TOP - 0.1, CAP_TOP + 0.5))], "UNION")

    # slider knob: 9 x 6 grip outside, a stem through the slot, a socket for the pot's lever
    knob = box("slider_knob", (-4.5, 4.5), (-3.0, 3.0), (0, 3.0))
    boolean(knob, [box("knob_stem", (-1.5, 1.5), (-SLOT_W / 2 + 0.3, SLOT_W / 2 - 0.3), (2.9, 3.0 + WALL + 1.2))], "UNION")
    parts["slider_knob"] = boolean(knob, [box("knob_socket", (-1.1, 1.1), (-0.6, 0.6), (3.7, 6.5))], "DIFFERENCE")

    # TPU pop-it insert: hollow domes that poke out through the back holes and invert when pressed
    base = cyl("popit_insert_TPU", POP_BASE_R, POP_BASE_T, at=(0, 0, POP_BASE_T / 2), seg=128)
    domes = [sphere(f"dome{i}", r - 0.35, (x, z, POP_BASE_T)) for i, (x, z, r) in enumerate(pop_layout())]
    boolean(base, domes, "UNION")
    voids = [sphere(f"void{i}", r - 0.35 - POP_WALL, (x, z, POP_BASE_T)) for i, (x, z, r) in enumerate(pop_layout())]
    boolean(base, voids, "DIFFERENCE")
    parts["popit_insert_TPU"] = boolean(base, [box("bed", (-40, 40), (-40, 40), (0, 20))], "INTERSECT")
    return parts


# ---------- export + checks ----------
def export(ob, folder):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(folder, ob.name + ".stl")
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.free()
    size = [round(v, 1) for v in ob.dimensions]
    print(f"{ob.name:22s} {size} mm  {vol / 1000:6.2f} cm3  non-manifold edges: {bad}")


# ---------- previews ----------
COLORS = {"front_shell": (1.0, 0.84, 0.5, 1), "back_shell": (0.4, 0.25, 1.0, 1), "popit_insert_TPU": (0.2, 0.75, 0.6, 1)}
CAP_COLOR = (1.0, 0.33, 1.0, 1)


def place_assembly(parts):
    """Copies of the caps and insert moved from print orientation to where they sit in the case."""
    rx = lambda deg: Matrix.Rotation(math.radians(deg), 4, "X")
    ry = lambda deg: Matrix.Rotation(math.radians(deg), 4, "Y")
    t = Matrix.Translation
    fy = -IHD + 1
    where = {
        "cap_ai_circle": t((-BTN_PITCH, fy, BTN_Z)) @ rx(90),
        "cap_dpad": t((0, fy, BTN_Z)) @ rx(90),
        "cap_record_square": t((BTN_PITCH, fy, BTN_Z)) @ rx(90),
        "cap_power": t((-inner_x(POWER_Z) + 1, 0, POWER_Z)) @ ry(-90),
        "cap_vol_up": t((-inner_x(VOLUP_Z) + 1, 0, VOLUP_Z)) @ ry(-90),
        "cap_vol_down": t((-inner_x(VOLDN_Z) + 1, 0, VOLDN_Z)) @ ry(-90),
        "slider_knob": t((RX + 3, 0, 0)) @ ry(-90),
        "popit_insert_TPU": t((0, IHD - POP_BASE_T, 0)) @ rx(-90),
    }
    placed = []
    for name, m in where.items():
        ob = copy(parts[name], name + "_placed")
        ob.matrix_world = m
        ob.hide_render = False
        ob.color = COLORS.get(name, CAP_COLOR)
        placed.append(ob)
    return placed


def render(folder, name, loc, scale, euler=None):
    """Orthographic render looking at the origin from loc (euler overrides the aim, e.g. straight up)."""
    scene = bpy.context.scene
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale, cam.data.clip_end = "ORTHO", scale, 2000
    cam.location = Vector(loc)
    cam.rotation_euler = euler or (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.filepath = os.path.join(folder, name + ".png")
    bpy.ops.render.render(write_still=True)


def render_all(folder, front, back, parts):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 900
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_cavity, sh.cavity_type = True, "BOTH"
    sh.show_object_outline = True
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.004, 0.03, 0.04)
    for ob, key in ((front, "front_shell"), (back, "back_shell")):
        ob.color = COLORS[key]
    for ob in parts.values():
        ob.hide_render = True
    placed = place_assembly(parts)

    render(folder, "1_front", (0, -400, 0), 105)
    render(folder, "2_back", (0, 400, 0), 105)
    render(folder, "3_left_side", (-400, 0, 0), 105)
    render(folder, "4_right_side", (400, 0, 0), 105)
    render(folder, "5_bottom", (0, 0, -400), 105, euler=(math.pi, 0, 0))
    render(folder, "6_iso", (260, -330, 220), 135)

    # exploded: pull the front shell and its caps forward
    front_bits = [front] + [o for o in placed if o.name.startswith(("cap_ai", "cap_dpad", "cap_record"))]
    for o in front_bits:
        o.location.y -= 28
    for o in placed:
        if o.name.startswith("popit"):
            o.location.y += 14
    render(folder, "7_exploded", (300, -330, 200), 170)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    stl_dir, png_dir = os.path.join(here, "stl"), os.path.join(here, "renders")
    os.makedirs(stl_dir, exist_ok=True)

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    front, back = build_shells()
    parts = build_caps()
    print("\npart                   size (x, y, z)        volume      mesh check")
    for ob in [front, back, *parts.values()]:
        export(ob, stl_dir)

    if "--render" in args:
        os.makedirs(png_dir, exist_ok=True)
        render_all(png_dir, front, back, parts)


main()
