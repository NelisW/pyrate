#!/usr/bin/env/python
"""
Pyrate - Optical raytracing based on Python

Copyright (C) 2014 Moritz Esslinger moritz.esslinger@web.de
               and Johannes Hartung j.hartung@gmx.net
               and    Uwe Lippmann  uwe.lippmann@web.de

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""



from PySide.QtGui import QInputDialog, QLineEdit, QComboBox


import FreeCADGui, FreeCAD


from Object_Functions import FunctionsObject
from TaskPanel_Functions_Add import FunctionsTaskPanelAdd

from Interface_Checks import *


class CreateFunctionTool:
    "Tool for creating optical system"

    def GetResources(self):
        return {"Pixmap"  : ":/icons/pyrate_func_icon.svg", # resource qrc file needed, and precompile with python-rcc
                "MenuText": "Create function ...",
                "Accel": "",
                "ToolTip": "Generates function object in document"
                }

    def IsActive(self):
        if FreeCAD.ActiveDocument == None:
            return False
        else:
            return True

    def Activated(self):

        doc = FreeCAD.ActiveDocument

        osobservers = []
        for obj in doc.Objects:
            if isOpticalSystemObserver(obj):
                osobservers.append(obj)

        panel = FunctionsTaskPanelAdd(doc, [oso.Label for oso in osobservers])
        FreeCADGui.Control.showDialog(panel)

            
FreeCADGui.addCommand('CreateFunctionsCommand', CreateFunctionTool())
