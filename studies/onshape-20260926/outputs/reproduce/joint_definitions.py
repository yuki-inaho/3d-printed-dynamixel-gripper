"""CAD-space kinematics, mm/degrees. Zero is the imported mid-pose, not hardware home."""
import math
X0=math.sqrt(24**2-14**2)
def slide(angle):
    t=math.radians(angle)
    return 14*math.cos(t)+math.sqrt(24**2-(14*math.sin(t))**2)-X0

JOINTS=[
    dict(name='joint1_yaw',a='base_link',b='shoulder_yaw',xyz=[0,0,20],axis='Z',rot=0,type='REVOLUTE'),
    dict(name='joint2_shoulder',a='shoulder_yaw',b='upper_arm',xyz=[-.2,0,56.3],axis='Y',rot=-90,type='REVOLUTE'),
    dict(name='joint3_elbow',a='upper_arm',b='forearm',xyz=[-.2,14.8,164.6],axis='Y',rot=90,type='REVOLUTE'),
    dict(name='joint4_wrist',a='forearm',b='wrist',xyz=[-.2,104.9,164.6],axis='Y',rot=90,type='REVOLUTE',limits=[-110,138]),
    dict(name='gripper_drive',a='wrist',b='gripper_crank',xyz=[-.2,164.9,164.6],axis='X',rot=-90,type='REVOLUTE',limits=[-45,65]),
    dict(name='jaw_left',a='wrist',b='jaw_l',xyz=[-.2,164.9,164.6],axis='Y',rot=90,type='SLIDER',limits=[slide(135),slide(25)]),
    dict(name='jaw_right',a='wrist',b='jaw_r',xyz=[-.2,164.9,164.6],axis='Y',rot=90,type='SLIDER',limits=[-slide(25),-slide(135)]),
    dict(name='coupler_left',a='gripper_crank',b='coupler_l',xyz=[-.2,164.9,178.6],axis='X',rot=-90,type='REVOLUTE'),
    dict(name='coupler_right',a='gripper_crank',b='coupler_r',xyz=[-.2,164.9,150.6],axis='X',rot=-90,type='REVOLUTE'),
    dict(name='camera_mount_fixed',a='wrist',b='camera_mount',xyz=[-.2,164.9,199.85],axis='Z',rot=0,type='FASTENED'),
    dict(name='camera_body_fixed',a='camera_mount',b='camera_body',xyz=[-.2,197,257],axis='Z',rot=0,type='FASTENED'),
    dict(name='closing_left',a='coupler_l',b='jaw_l',xyz=[-.2-X0,192.9,164.6],axis='X',rot=-90,type='BALL',closing=True),
    dict(name='closing_right',a='coupler_r',b='jaw_r',xyz=[-.2+X0,192.9,164.6],axis='X',rot=-90,type='BALL',closing=True),
]
