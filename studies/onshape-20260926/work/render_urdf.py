import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outputs/robot"))
import matplotlib
from validate_robot import *

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

robot = ET.parse(ROOT / "robot.urdf").getroot()
fig = plt.figure(figsize=(16, 8), facecolor="#f2f4f7")
for idx, theta in enumerate([90, 25, 90, 135]):
    ax = fig.add_subplot(1, 4, idx + 1, projection="3d")
    ax.set_facecolor("#f2f4f7")
    poses = fk(robot, joint_states(theta))
    points = []
    for link in robot.findall("link"):
        name = link.get("name")
        vis = link.find("visual")
        if vis is None:
            continue
        if idx and name not in [
            "wrist",
            "gripper_crank",
            "jaw_l",
            "jaw_r",
            "coupler_l",
            "coupler_r",
        ]:
            continue
        mesh = trimesh.load_mesh(ROOT / vis.find("geometry/mesh").get("filename"), process=False)
        v = trimesh.transform_points(mesh.vertices, poses[name] @ origin(vis.find("origin")))
        color = np.array(list(map(float, vis.find("material/color").get("rgba").split())))[:3]
        normals = np.cross(
            v[mesh.faces[:, 1]] - v[mesh.faces[:, 0]], v[mesh.faces[:, 2]] - v[mesh.faces[:, 0]]
        )
        normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-20)
        shade = 0.4 + 0.6 * np.maximum(normals @ np.array([0.4, -0.5, 0.768]), 0)
        poly = Poly3DCollection(
            v[mesh.faces],
            facecolors=np.clip(color[None, :] * shade[:, None], 0, 1),
            edgecolor="none",
            rasterized=True,
        )
        ax.add_collection3d(poly)
        points.append(v)
    v = np.vstack(points)
    mid = (v.min(axis=0) + v.max(axis=0)) / 2
    span = (v.max(axis=0) - v.min(axis=0)).max() * 1.05
    for axis, m in zip([ax.set_xlim, ax.set_ylim, ax.set_zlim], mid):
        axis(m - span / 2, m + span / 2)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=25 if idx == 0 else 50, azim=-50 if idx == 0 else -80)
    ax.set_axis_off()
    ax.set_title(
        "Whole robot (mid)" if idx == 0 else f"PG3 {theta} deg\nopening {opening_mm(theta):.2f} mm",
        fontsize=13,
        pad=0,
    )
fig.suptitle("URDF mesh / forward-kinematics verification", fontsize=20, y=0.87)
fig.text(
    0.5,
    0.15,
    "Kinematic model only. Gripper detail panels omit the camera assembly for visibility.",
    ha="center",
    fontsize=12,
)
fig.savefig(ROOT.parent / "urdf-kinematics.png", dpi=180, bbox_inches="tight")
print("rendered")
