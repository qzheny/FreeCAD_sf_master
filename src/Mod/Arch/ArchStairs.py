#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2013                                                    *  
#*   Yorik van Havre <yorik@uncreated.net>                                 *  
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

__title__="FreeCAD Arch Stairs"
__author__ = "Yorik van Havre"
__url__ = "http://www.freecadweb.org"

import FreeCAD,FreeCADGui,ArchComponent,ArchCommands,Draft,DraftVecUtils,math
from FreeCAD import Vector
from DraftTools import translate
from PySide import QtCore


def makeStairs(base=None,length=4.5,width=1,height=3,steps=17,name=translate("Arch","Stairs")):
    """makeStairs([base,length,width,height,steps]): creates a Stairs
    objects with given attributes."""
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython",name)
    _Stairs(obj)
    _ViewProviderStairs(obj.ViewObject)
    if base:
        obj.Base = base
    obj.Length = length
    obj.Width = width
    obj.Height = height
    obj.NumberOfSteps = steps


class _CommandStairs:
    "the Arch Stairs command definition"
    def GetResources(self):
        return {'Pixmap'  : 'Arch_Stairs',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Arch_Stairs","Stairs"),
                'Accel': "S, R",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Arch_Space","Creates a stairs objects")}

    def Activated(self):
        FreeCAD.ActiveDocument.openTransaction(translate("Arch","Create Stairs"))
        FreeCADGui.doCommand("import Arch")
        if len(FreeCADGui.Selection.getSelection()) == 1:
            n = FreeCADGui.Selection.getSelection()[0].Name
            FreeCADGui.doCommand("Arch.makeStairs(base=FreeCAD.ActiveDocument."+n+")")
        else:
            FreeCADGui.doCommand("Arch.makeStairs()")
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()


class _Stairs(ArchComponent.Component):
    "A stairs object"
    def __init__(self,obj):
        ArchComponent.Component.__init__(self,obj)
        
        # http://en.wikipedia.org/wiki/Stairs
        
        # base properties
        obj.addProperty("App::PropertyLength","Length","Arch",
                        translate("Arch","The length of these stairs, if no baseline is defined"))
        obj.addProperty("App::PropertyLength","Width","Arch",
                        translate("Arch","The width of these stairs"))
        obj.addProperty("App::PropertyLength","Height","Arch",
                        translate("Arch","The total height of these stairs"))
        obj.addProperty("App::PropertyEnumeration","Align","Arch",
                        translate("Arch","The alignment of these stairs on their baseline, if applicable"))
                        
        # steps properties
        obj.addProperty("App::PropertyInteger","NumberOfSteps","Steps",
                        translate("Arch","The number of risers in these stairs"))
        obj.addProperty("App::PropertyLength","TreadDepth","Steps",
                        translate("Arch","The depth of the treads of these stairs"))
        obj.addProperty("App::PropertyLength","RiserHeight","Steps",
                        translate("Arch","The height of the risers of these stairs"))
        obj.addProperty("App::PropertyLength","Nosing","Steps",
                        translate("Arch","The size of the nosing"))
        obj.addProperty("App::PropertyLength","TreadThickness","Steps",
                        translate("Arch","The thickness of the treads"))
        obj.addProperty("App::PropertyLength","BlondelRatio","Steps",
                        translate("Arch","The Blondel ratio, must be between 62 and 64cm or 24.5 and 25.5in"))
                        
        # structural properties
        obj.addProperty("App::PropertyEnumeration","Landings","Structure",
                        translate("Arch","The type of landings of these stairs"))
        obj.addProperty("App::PropertyEnumeration","Winders","Structure",
                        translate("Arch","The type of winders in these stairs"))
        obj.addProperty("App::PropertyEnumeration","Structure","Structure",
                        translate("Arch","The type of structure of these stairs"))
        obj.addProperty("App::PropertyLength","StructureThickness","Structure",
                        translate("Arch","The thickness of the massive structure or of the stringers"))
        obj.addProperty("App::PropertyLength","StringerWidth","Structure",
                        translate("Arch","The width of the stringers"))
        obj.addProperty("App::PropertyLength","StructureOffset","Structure",
                        translate("Arch","The offset between the border of the stairs and the structure"))
                        
        obj.Align = ['Left','Right','Center']
        obj.Landings = ["None","At center","At each corner"]
        obj.Winders = ["None","All","Corners strict","Corners relaxed"]
        obj.Structure = ["None","Massive","One stringer","Two stringers"]
        obj.setEditorMode("TreadDepth",1)
        obj.setEditorMode("RiserHeight",1)
        obj.setEditorMode("BlondelRatio",1)
        self.Type = "Stairs"


    def execute(self,obj):

        "constructs the shape of the stairs"

        import Part
        self.steps = []
        self.structures = []
        pl = obj.Placement
        landings = 0

        # base tests
        if not obj.Width:
            return
        if not obj.Height:
            if not obj.Base:
                return
        if obj.NumberOfSteps < 2:
            return
        if obj.Base:
            if not obj.Base.isDerivedFrom("Part::Feature"):
                return
            if obj.Base.Shape.Solids:
                obj.Shape = obj.Base.Shape.copy()
                obj.Placement = FreeCAD.Placement(obj.Base.Placement).multiply(pl)
                obj.TreadDepth = 0.0
                obj.RiserHeight = 0.0
                return
            if not obj.Base.Shape.Edges:
                return
            if obj.Base.Shape.Faces:
                return
            if (len(obj.Base.Shape.Edges) == 1): 
                edge = obj.Base.Shape.Edges[0]
                if isinstance(edge.Curve,Part.Line):
                    if obj.Landings == "At center":
                        landings = 1
                        self.makeStraightStairsWithLanding(obj,edge)                
                    else:
                        self.makeStraightStairs(obj,edge)
                else:
                    if obj.Landings == "At center":
                        landings = 1
                        self.makeCurvedStairsWithLandings(obj,edge)
                    else:
                        self.makeCurvedStairs(obj,edge)
        else:
            if not obj.Length:
                return
            edge = Part.Line(Vector(0,0,0),Vector(obj.Length,0,0)).toShape()
            if obj.Landings == "At center":
                landings = 1
                self.makeStraightStairsWithLanding(obj,edge)
            else:
                self.makeStraightStairs(obj,edge)

        if self.structures or self.steps:
            shape = Part.makeCompound(self.structures + self.steps)
            shape = self.processSubShapes(obj,shape,pl)
            obj.Shape = shape
            obj.Placement = pl

        # compute step data
        if obj.NumberOfSteps > 1:
            l = obj.Length
            h = obj.Height
            if obj.Base:
                if obj.Base.isDerivedFrom("Part::Feature"):
                    l = obj.Base.Shape.Length
                    if obj.Base.Shape.BoundBox.ZLength:
                        h = obj.Base.Shape.BoundBox.ZLength
            obj.TreadDepth = float(l-(landings*obj.Width))/(obj.NumberOfSteps-(1+landings))
            obj.RiserHeight = float(h)/obj.NumberOfSteps
            obj.BlondelRatio = obj.RiserHeight*2+obj.TreadDepth


    def align(self,basepoint,align,widthvec):
        "moves a given basepoint according to the alignment"
        if align == "Center":
            basepoint = basepoint.add(DraftVecUtils.scale(widthvec,-0.5))
        elif align == "Right":
            basepoint = basepoint.add(DraftVecUtils.scale(widthvec,-1))
        return basepoint

    def makeStraightLanding(self,obj,edge,numberofsteps=None):

        "builds a landing from a straight edge"

        # general data
        if not numberofsteps:
            numberofsteps = obj.NumberOfSteps
        import Part,DraftGeomUtils
        v = DraftGeomUtils.vec(edge)
        vLength = Vector(v.x,v.y,0)
        vWidth = vWidth = DraftVecUtils.scaleTo(vLength.cross(Vector(0,0,1)),obj.Width)
        vBase = edge.Vertexes[0].Point
        vNose = DraftVecUtils.scaleTo(vLength,-abs(obj.Nosing))
        h = obj.Height
        l = obj.Length
        if obj.Base:
            if obj.Base.isDerivedFrom("Part::Feature"):
                l = obj.Base.Shape.Length
                if obj.Base.Shape.BoundBox.ZLength:
                    h = obj.Base.Shape.BoundBox.ZLength
        fLength = float(l-obj.Width)/(numberofsteps-2)
        fHeight = float(h)/numberofsteps
        a = math.atan(fHeight/fLength)
        print "landing data:",fLength,":",fHeight

        # step
        p1 = self.align(vBase,obj.Align,vWidth)
        p1 = p1.add(vNose).add(Vector(0,0,-abs(obj.TreadThickness)))
        p2 = p1.add(DraftVecUtils.neg(vNose)).add(vLength)
        p3 = p2.add(vWidth)
        p4 = p3.add(DraftVecUtils.neg(vLength)).add(vNose)
        step = Part.Face(Part.makePolygon([p1,p2,p3,p4,p1]))
        if obj.TreadThickness:
            step = step.extrude(Vector(0,0,abs(obj.TreadThickness)))
        self.steps.append(step)

        # structure
        lProfile = []
        struct = None
        p7 = None
        p1 = p1.add(DraftVecUtils.neg(vNose))
        p2 = p1.add(Vector(0,0,-fHeight)).add(Vector(0,0,-obj.StructureThickness/math.cos(a)))
        resheight = p1.sub(p2).Length - obj.StructureThickness
        reslength = resheight / math.tan(a)
        p3 = p2.add(DraftVecUtils.scaleTo(vLength,reslength)).add(Vector(0,0,resheight))
        p6 = p1.add(vLength)
        if obj.TreadThickness:
            p7 = p6.add(Vector(0,0,obj.TreadThickness))

        reslength = fLength + (obj.StructureThickness/math.sin(a)-(fHeight-obj.TreadThickness)/math.tan(a))
        if p7:
            p5 = p7.add(DraftVecUtils.scaleTo(vLength,reslength))
        else:
            p5 = p6.add(DraftVecUtils.scaleTo(vLength,reslength))
        resheight = obj.StructureThickness+obj.TreadThickness
        reslength = resheight/math.tan(a)
        p4 = p5.add(DraftVecUtils.scaleTo(vLength,-reslength)).add(Vector(0,0,-resheight))
        if obj.Structure == "Massive":
            if obj.StructureThickness:
                if p7:
                    struct = Part.Face(Part.makePolygon([p1,p2,p3,p4,p5,p7,p6,p1]))
                else:
                    struct = Part.Face(Part.makePolygon([p1,p2,p3,p4,p5,p6,p1]))
                evec = vWidth
                if obj.StructureOffset:
                    mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                    struct.translate(mvec)
                    evec = DraftVecUtils.scaleTo(evec,evec.Length-(2*mvec.Length))
                struct = struct.extrude(evec)
        elif obj.Structure in ["One stringer","Two stringers"]:
            if obj.StringerWidth and obj.StructureThickness:
                p1b = p1.add(Vector(0,0,-fHeight))
                reslength = fHeight/math.tan(a)
                p1c = p1.add(DraftVecUtils.scaleTo(vLength,reslength))
                p5b = None
                p5c = None
                if obj.TreadThickness:
                    reslength = obj.StructureThickness/math.sin(a)
                    p5b = p5.add(DraftVecUtils.scaleTo(vLength,-reslength))
                    reslength = obj.TreadThickness/math.tan(a)
                    p5c = p5b.add(DraftVecUtils.scaleTo(vLength,-reslength)).add(Vector(0,0,-obj.TreadThickness))
                    pol = Part.Face(Part.makePolygon([p1c,p1b,p2,p3,p4,p5,p5b,p5c,p1c]))
                else:
                    pol = Part.Face(Part.makePolygon([p1c,p1b,p2,p3,p4,p5,p1c]))
                evec = DraftVecUtils.scaleTo(vWidth,obj.StringerWidth)
                if obj.Structure == "One stringer":
                    if obj.StructureOffset:
                        mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                    else:
                        mvec = DraftVecUtils.scaleTo(vWidth,(vWidth.Length/2)-obj.StringerWidth/2)
                    pol.translate(mvec)
                    struct = pol.extrude(evec)
                elif obj.Structure == "Two stringers":
                    pol2 = pol.copy()
                    if obj.StructureOffset:
                        mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                        pol.translate(mvec)
                        mvec = vWidth.add(mvec.negative())
                        pol2.translate(mvec)
                    else:
                        pol2.translate(vWidth)
                    s1 = pol.extrude(evec)
                    s2 = pol2.extrude(evec.negative())
                    struct = Part.makeCompound([s1,s2])
        if struct:
            self.structures.append(struct)


    def makeStraightStairs(self,obj,edge,numberofsteps=None):

        "builds a simple, straight staircase from a straight edge"

        # general data
        import Part,DraftGeomUtils
        if not numberofsteps:
            numberofsteps = obj.NumberOfSteps
        v = DraftGeomUtils.vec(edge)
        vLength = DraftVecUtils.scaleTo(v,float(edge.Length)/(numberofsteps-1))
        vLength = Vector(vLength.x,vLength.y,0)
        if round(v.z,Draft.precision()) != 0:
            h = v.z
        else:
            h = obj.Height
        vHeight = Vector(0,0,float(h)/numberofsteps)
        vWidth = DraftVecUtils.scaleTo(vLength.cross(Vector(0,0,1)),obj.Width)
        vBase = edge.Vertexes[0].Point
        vNose = DraftVecUtils.scaleTo(vLength,-abs(obj.Nosing))
        a = math.atan(vHeight.Length/vLength.Length)
        print "stair data:",vLength.Length,":",vHeight.Length

        # steps
        for i in range(numberofsteps-1):
            p1 = vBase.add((Vector(vLength).multiply(i)).add(Vector(vHeight).multiply(i+1)))
            p1 = self.align(p1,obj.Align,vWidth)
            p1 = p1.add(vNose).add(Vector(0,0,-abs(obj.TreadThickness)))
            p2 = p1.add(DraftVecUtils.neg(vNose)).add(vLength)
            p3 = p2.add(vWidth)
            p4 = p3.add(DraftVecUtils.neg(vLength)).add(vNose)
            step = Part.Face(Part.makePolygon([p1,p2,p3,p4,p1]))
            if obj.TreadThickness:
                step = step.extrude(Vector(0,0,abs(obj.TreadThickness)))
            self.steps.append(step)

        # structure
        lProfile = []
        struct = None
        if obj.Structure == "Massive":
            if obj.StructureThickness:
                for i in range(numberofsteps-1):
                    if not lProfile:
                        lProfile.append(vBase)
                    last = lProfile[-1]
                    if len(lProfile) == 1:
                        last = last.add(Vector(0,0,-abs(obj.TreadThickness)))
                    lProfile.append(last.add(vHeight))
                    lProfile.append(lProfile[-1].add(vLength))
                resHeight1 = obj.StructureThickness/math.cos(a)
                lProfile.append(lProfile[-1].add(Vector(0,0,-resHeight1)))
                resHeight2 = ((numberofsteps-1)*vHeight.Length)-(resHeight1+obj.TreadThickness)
                resLength = (vLength.Length/vHeight.Length)*resHeight2
                h = DraftVecUtils.scaleTo(vLength,-resLength)
                lProfile.append(lProfile[-1].add(Vector(h.x,h.y,-resHeight2)))
                lProfile.append(vBase)
                #print lProfile
                pol = Part.makePolygon(lProfile)
                struct = Part.Face(pol)
                evec = vWidth
                if obj.StructureOffset:
                    mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                    struct.translate(mvec)
                    evec = DraftVecUtils.scaleTo(evec,evec.Length-(2*mvec.Length))
                struct = struct.extrude(evec)
        elif obj.Structure in ["One stringer","Two stringers"]:
            if obj.StringerWidth and obj.StructureThickness:
                hyp = math.sqrt(vHeight.Length**2 + vLength.Length**2)
                l1 = Vector(vLength).multiply(numberofsteps-1)
                h1 = Vector(vHeight).multiply(numberofsteps-1).add(Vector(0,0,-abs(obj.TreadThickness)))
                p1 = vBase.add(l1).add(h1)
                p1 = self.align(p1,obj.Align,vWidth)
                lProfile.append(p1)
                h2 = (obj.StructureThickness/vLength.Length)*hyp
                lProfile.append(lProfile[-1].add(Vector(0,0,-abs(h2))))
                h3 = lProfile[-1].z-vBase.z
                l3 = (h3/vHeight.Length)*vLength.Length
                v3 = DraftVecUtils.scaleTo(vLength,-l3)
                lProfile.append(lProfile[-1].add(Vector(0,0,-abs(h3))).add(v3))
                l4 = (obj.StructureThickness/vHeight.Length)*hyp
                v4 = DraftVecUtils.scaleTo(vLength,-l4)
                lProfile.append(lProfile[-1].add(v4))
                lProfile.append(lProfile[0])
                #print lProfile
                pol = Part.makePolygon(lProfile)
                pol = Part.Face(pol)
                evec = DraftVecUtils.scaleTo(vWidth,obj.StringerWidth)
                if obj.Structure == "One stringer":
                    if obj.StructureOffset:
                        mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                    else:
                        mvec = DraftVecUtils.scaleTo(vWidth,(vWidth.Length/2)-obj.StringerWidth/2)
                    pol.translate(mvec)
                    struct = pol.extrude(evec)
                elif obj.Structure == "Two stringers":
                    pol2 = pol.copy()
                    if obj.StructureOffset:
                        mvec = DraftVecUtils.scaleTo(vWidth,obj.StructureOffset)
                        pol.translate(mvec)
                        mvec = vWidth.add(mvec.negative())
                        pol2.translate(mvec)
                    else:
                        pol2.translate(vWidth)
                    s1 = pol.extrude(evec)
                    s2 = pol2.extrude(evec.negative())
                    struct = Part.makeCompound([s1,s2])
        if struct:
            self.structures.append(struct)


    def makeStraightStairsWithLanding(self,obj,edge):
        
        "builds a straight staircase with a landing in the middle"

        if obj.NumberOfSteps < 3:
            return
        import Part,DraftGeomUtils
        v = DraftGeomUtils.vec(edge)
        reslength = edge.Length - obj.Width
        vLength = DraftVecUtils.scaleTo(v,float(reslength)/(obj.NumberOfSteps-2))
        vLength = Vector(vLength.x,vLength.y,0)
        vWidth = DraftVecUtils.scaleTo(vLength.cross(Vector(0,0,1)),obj.Width)
        p1 = edge.Vertexes[0].Point
        if round(v.z,Draft.precision()) != 0:
            h = v.z
        else:
            h = obj.Height
        hstep = h/obj.NumberOfSteps
        landing = obj.NumberOfSteps/2
        p2 = p1.add(DraftVecUtils.scale(vLength,landing-1).add(Vector(0,0,landing*hstep)))
        p3 = p2.add(DraftVecUtils.scaleTo(vLength,obj.Width))
        p4 = p3.add(DraftVecUtils.scale(vLength,obj.NumberOfSteps-(landing+1)).add(Vector(0,0,(obj.NumberOfSteps-landing)*hstep)))
        self.makeStraightStairs(obj,Part.Line(p1,p2).toShape(),landing)
        self.makeStraightLanding(obj,Part.Line(p2,p3).toShape())
        self.makeStraightStairs(obj,Part.Line(p3,p4).toShape(),obj.NumberOfSteps-landing)


    def makeCurvedStairs(self,obj,edge):
        print "Not yet implemented!"

    def makeCurvedStairsWithLanding(self,obj,edge):
        print "Not yet implemented!"



class _ViewProviderStairs(ArchComponent.ViewProviderComponent):
    "A View Provider for Stairs"
    def __init__(self,vobj):
        ArchComponent.ViewProviderComponent.__init__(self,vobj)
        
    def getIcon(self):
        import Arch_rc
        return ":/icons/Arch_Stairs_Tree.svg"


FreeCADGui.addCommand('Arch_Stairs',_CommandStairs())
