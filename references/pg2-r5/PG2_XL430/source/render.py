"""Render the exact CadQuery solids using VTK, never a generative illustration."""
from __future__ import annotations
import vtk,math,sys
import numpy as np
from vtk.util.numpy_support import numpy_to_vtk
from PIL import Image,ImageDraw,ImageFont
from design import *

def actor(shape,color):
 vs,fs=shape.tessellate(.12,.18)
 pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(np.array([v.toTuple() for v in vs],dtype=float)))
 cells=vtk.vtkCellArray()
 for f in fs:
  cells.InsertNextCell(3)
  for j in f:cells.InsertCellPoint(j)
 data=vtk.vtkPolyData();data.SetPoints(pts);data.SetPolys(cells)
 normal=vtk.vtkPolyDataNormals();normal.SetInputData(data);normal.ComputePointNormalsOn();normal.SplittingOn();normal.SetFeatureAngle(35);normal.Update()
 mp=vtk.vtkPolyDataMapper();mp.SetInputConnection(normal.GetOutputPort())
 ac=vtk.vtkActor();ac.SetMapper(mp);ac.GetProperty().SetColor(color);ac.GetProperty().SetSpecular(.25);ac.GetProperty().SetSpecularPower(25)
 return ac

def render(items,path,cam=(150,110,210),target=(0,0,5),up=(0,1,0),scale=85,perspective=False,size=(1500,1150),fov=45):
 ren=vtk.vtkRenderer();ren.SetBackground(.965,.97,.98)
 for it in items:ren.AddActor(actor(it.shape,it.color))
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(*size);win.SetMultiSamples(4);win.AddRenderer(ren)
 camera=ren.GetActiveCamera();camera.SetPosition(*cam);camera.SetFocalPoint(*target);camera.SetViewUp(*up)
 if perspective:camera.SetViewAngle(fov)
 else:camera.ParallelProjectionOn();camera.SetParallelScale(scale)
 ren.ResetCameraClippingRange();win.Render()
 filt=vtk.vtkWindowToImageFilter();filt.SetInput(win);filt.SetInputBufferTypeToRGB();filt.ReadFrontBufferOff();filt.Update()
 wr=vtk.vtkPNGWriter();wr.SetFileName(str(path));wr.SetInputConnection(filt.GetOutputPort());wr.Write();win.Finalize()

