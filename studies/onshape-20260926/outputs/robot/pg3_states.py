"""Nonlinear PG3 closure for this URDF. Angles radians, slider distances metres.

CAD theta is 25..135 degrees; exported drive q = radians(90 - theta).
This is geometric joint-state coupling, not hardware control or dynamics.
"""
import math

def joint_states(theta_deg=90):
    if not math.isfinite(theta_deg) or not 25 <= theta_deg <= 135:
        raise ValueError('theta_deg must be finite and in [25, 135]')
    theta=math.radians(theta_deg)
    x0=math.sqrt(24**2-14**2)
    x=14*math.cos(theta)+math.sqrt(24**2-(14*math.sin(theta))**2)
    drive_delta=theta-math.pi/2
    link_delta=math.atan2(-14*math.sin(theta), x-14*math.cos(theta))-math.atan2(-14,x0)
    return dict(joint1_yaw=0.,joint2_shoulder=0.,joint3_elbow=0.,joint4_wrist=0.,
                gripper_drive=-drive_delta,jaw_left=(x-x0)/1000,jaw_right=-(x-x0)/1000,
                coupler_left=drive_delta-link_delta,coupler_right=drive_delta-link_delta)

def opening_mm(theta_deg=90):
    q=joint_states(theta_deg)
    return 2*(math.sqrt(24**2-14**2)+1000*q['jaw_left']-11.5)

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('theta',type=float,nargs='?',default=90)
    t=p.parse_args().theta
    print(json.dumps({'theta_deg':t,'opening_mm':opening_mm(t),'joint_positions':joint_states(t)},indent=2))
