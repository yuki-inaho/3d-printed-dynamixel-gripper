"""Pinhole projection and first-hit mesh visibility of actual jaw-tip surfaces.

The optics/PCB dimensions are explicit assumptions, not a calibrated camera.
Visibility uses tessellated CAD, with self-occlusion included. It is sampled,
not a guarantee about specular surfaces, image exposure, objects, or focus.
"""
from __future__ import annotations
import math
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from design import camera_basis, camera_optical_center, PIVOT


def tessellate(shape):
    vs,fs=shape.tessellate(.04,.10)
    v=np.array([p.toTuple() for p in vs],dtype=float)
    f=np.array(fs,dtype=np.int64)
    return v,f


def polydata(vertices,faces):
    p=vtk.vtkPoints();p.SetData(numpy_to_vtk(vertices,deep=True))
    cells=vtk.vtkCellArray()
    cells.SetCells(len(faces),numpy_to_vtkIdTypeArray(np.c_[np.full(len(faces),3),faces].ravel(),deep=True))
    data=vtk.vtkPolyData();data.SetPoints(p);data.SetPolys(cells)
    return data


def combine(meshes):
    vs,fs,offset=[],[],0
    for v,f in meshes:
        vs.append(v);fs.append(f+offset);offset+=len(v)
    return np.concatenate(vs),np.concatenate(fs)


def turn_vertices(v,deg):
    a=math.radians(-deg)
    R=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])
    return (v-PIVOT)@R.T+PIVOT


def project(points, c):
    r,up,d=camera_basis(c)
    dv=np.asarray(points)-camera_optical_center(c)
    depth=dv@d
    uv=np.column_stack((dv@r,dv@up))/depth[:,None]
    ndc=uv/np.tan(np.radians([c['assumed_hfov_deg'],c['assumed_vfov_deg']])/2)
    return ndc,depth


def tip_samples(v,f,max_count=240):
    tri=v[f];centres=tri.mean(axis=1)
    selected=np.flatnonzero(centres[:,1]>=25.)
    if len(selected)<8:raise ValueError('Cannot identify distal jaw surface from measured Y >= 25 mm region')
    if len(selected)>max_count:selected=selected[np.linspace(0,len(selected)-1,max_count).astype(int)]
    pts=centres[selected]
    normals=np.cross(tri[selected,1]-tri[selected,0],tri[selected,2]-tri[selected,0])
    norms=np.linalg.norm(normals,axis=1)
    keep=norms>1e-12
    verts=tri[np.flatnonzero(centres[:,1]>=25.)].reshape(-1,3)
    return pts[keep],normals[keep]/norms[keep,None],verts


def visible_samples(points,normals,vertices,c,locator):
    lens=camera_optical_center(c)
    ndc,depth=project(points,c)
    facing=np.einsum('ij,ij->i',normals,lens-points)>1e-8
    inside=np.all(np.abs(ndc)<=1,axis=1)&(depth>0)
    eligible=np.flatnonzero(facing&inside)
    visible=[]
    for index in eligible:
        target=points[index]
        vec=target-lens
        start=lens+vec*(.002/np.linalg.norm(vec))
        t=vtk.mutable(0.);sub=vtk.mutable(0);cid=vtk.mutable(0)
        hit=[0.,0.,0.];pc=[0.,0.,0.]
        ok=locator.IntersectWithLine(start,target+vec*.0001,1e-7,t,hit,pc,sub,cid)
        if ok and np.linalg.norm(np.array(hit)-target)<.02:visible.append(int(index))
    boundary,bd=project(vertices,c)
    maxabs=np.max(np.abs(boundary),axis=0)
    return {
        'sample_points':len(points), 'front_facing_points':int(facing.sum()),
        'in_fov_sample_points':int(inside.sum()),'visible_surface_witnesses':len(visible),
        'max_tip_abs_ndc_xy':maxabs.tolist(),
        'tip_region_all_vertices_in_fov':bool(np.all(maxabs<=1)&np.all(bd>0)),
        'visible_indices':visible,
        'passed':len(visible)>=8 and bool(np.all(maxabs<=1)&np.all(bd>0))}


def check_vision(d,angles=None,items_override=None):
    c=d.config
    from design import hand_items
    items=items_override if items_override is not None else hand_items(d,0)
    fixed,rotor=[],[]
    target={}
    for i in items:
        if not i.shape.Solids():continue
        v,f=tessellate(i.world)
        (rotor if i.role=='rotor' else fixed).append((v,f))
        if i.key==f'original_{d.static_index:03d}':target['static']=tip_samples(v,f)
        if i.key==f'original_{d.moving_index:03d}':target['moving']=tip_samples(v,f)
    fm=combine(fixed);rm=combine(rotor)
    result=[]
    if angles is None:
        angles=list(np.arange(0,c['opening_max_deg']+1e-8,c['vision_sample_step_deg']))
        if angles[-1] < c['opening_max_deg']:angles.append(c['opening_max_deg'])
    for a in angles:
        v,f=combine([fm,(turn_vertices(rm[0],a),rm[1])])
        loc=vtk.vtkStaticCellLocator();loc.SetDataSet(polydata(v,f));loc.BuildLocator()
        entry={'opening_deg':float(a),'jaws':{}}
        for jaw,(pts,ns,verts) in target.items():
            if jaw=='moving':
                pp=turn_vertices(pts,a);vv=turn_vertices(verts,a)
                nn=turn_vertices(ns+PIVOT,a)-PIVOT
            else:pp,nn,vv=pts,ns,verts
            entry['jaws'][jaw]=visible_samples(pp,nn,vv,c,loc)
        entry['passed']=all(x['passed'] for x in entry['jaws'].values())
        result.append(entry)
    return {'method':'CAD-triangle tip region Y>=25 mm; first-hit ray including self-occlusion; pinhole optics assumptions',
            'assumed_hfov_deg':c['assumed_hfov_deg'],'assumed_vfov_deg':c['assumed_vfov_deg'],
            'lens_center_hand_mm':camera_optical_center(c).tolist(),'image_right_hand':camera_basis(c)[0].tolist(),
            'forward_hand':camera_basis(c)[2].tolist(),'angles':result,
            'passed':all(x['passed'] for x in result),
            'not_verified':['Actual lens FOV/distortion/cropping/focus','Sensor or USB-connector envelope','Occlusion by grasped objects','Exposure, reflectivity, texture and real-world image quality','Visibility between sampled angles']}


def render_camera(items,c,path,size=(1280,960)):
    renderer=vtk.vtkRenderer();renderer.SetBackground(.968,.975,.982)
    for i in items:
        if not i.shape.Solids():continue
        v,f=tessellate(i.world)
        normals=vtk.vtkPolyDataNormals();normals.SetInputData(polydata(v,f));normals.SetFeatureAngle(35)
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
        a=vtk.vtkActor();a.SetMapper(mapper)
        a.GetProperty().SetColor(*i.color);a.GetProperty().SetAmbient(.35);a.GetProperty().SetDiffuse(.65)
        renderer.AddActor(a)
    lens=camera_optical_center(c);_,up,d=camera_basis(c)
    cam=renderer.GetActiveCamera();cam.SetPosition(lens);cam.SetFocalPoint(lens+d*100);cam.SetViewUp(up)
    cam.SetClippingRange(.05,2000)
    # Independent horizontal/vertical focal lengths support explicit FOV in any
    # raster aspect ratio. This is not a claim about a real sensor resolution.
    near,far=.05,2000.
    m=vtk.vtkMatrix4x4();m.Zero()
    m.SetElement(0,0,1/math.tan(math.radians(c['assumed_hfov_deg']/2)))
    m.SetElement(1,1,1/math.tan(math.radians(c['assumed_vfov_deg']/2)))
    m.SetElement(2,2,-(far+near)/(far-near));m.SetElement(2,3,-2*far*near/(far-near));m.SetElement(3,2,-1)
    cam.SetExplicitProjectionTransformMatrix(m);cam.UseExplicitProjectionTransformMatrixOn()
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(True);win.SetSize(*size);win.AddRenderer(renderer);win.SetMultiSamples(4);win.Render()
    grab=vtk.vtkWindowToImageFilter();grab.SetInput(win);grab.ReadFrontBufferOff();grab.Update()
    wr=vtk.vtkPNGWriter();wr.SetFileName(str(path));wr.SetInputConnection(grab.GetOutputPort());wr.Write();win.Finalize()
