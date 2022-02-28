"""Copyright (c) 2022 VIKTOR B.V.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

VIKTOR B.V. PROVIDES THIS SOFTWARE ON AN "AS IS" BASIS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from io import BytesIO
from pathlib import Path

import numpy as np
from shapely.geometry import LineString
from shapely.ops import substring

from viktor import Color
from viktor.core import ViktorController
from viktor.external.scia import LoadCase
from viktor.external.scia import LoadCombination
from viktor.external.scia import LoadGroup
from viktor.external.scia import Material as SciaMaterial
from viktor.external.scia import Model as SciaModel
from viktor.external.scia import ResultType
from viktor.external.scia import SciaAnalysis
from viktor.external.scia import SurfaceLoad
from viktor.geometry import CircularExtrusion
from viktor.geometry import Extrusion
from viktor.geometry import GeoPoint
from viktor.geometry import GeoPolygon
from viktor.geometry import Group
from viktor.geometry import Line
from viktor.geometry import Material
from viktor.geometry import Point
from viktor.geometry import Sphere
from viktor.result import DownloadResult
from viktor.views import GeometryResult
from viktor.views import GeometryView
from viktor.views import MapPolygon
from viktor.views import MapPolyline
from viktor.views import MapResult
from viktor.views import MapView
from viktor.views import PDFResult
from viktor.views import PDFView
from .parametrization import TunnelParametrization


class TunnelController(ViktorController):
    """Controller class which acts as interface for the Sample entity type."""
    label = "Tunnel"
    parametrization = TunnelParametrization
    viktor_convert_entity_field = True

    @MapView('Map', duration_guess=2)
    def visualize_tunnel(self, params, **kwargs) -> MapResult:
        """Set the map view on which the line can be drawn for the tunnel and segments are filled in"""
        if not params.step1.geo_polyline:
            return MapResult([])

        features = []

        line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        segment_length = line_string.length / params.step1.segments
        for i in range(0, params.step1.segments):
            begin = i * segment_length
            end = (i + 1) * segment_length
            line_string_sub = substring(line_string, begin, end)
            left_line = line_string_sub.parallel_offset(40, 'left')
            right_line = line_string_sub.parallel_offset(40, 'right')
            linestring_points = list(left_line.coords) + list(right_line.coords)
            polygon = GeoPolygon(*[GeoPoint.from_rd(pt) for pt in linestring_points])
            features.append(MapPolygon.from_geo_polygon(polygon))

        features.append(MapPolyline.from_geo_polyline(params.step1.geo_polyline))
        return MapResult(features)

    @GeometryView("3D", duration_guess=1)
    def visualize_tunnel_segment(self, params, **kwargs):
        """"create a visualization of a tunnel segment"""
        geometry_group = self.create_visualization_geometries(params)
        return GeometryResult(geometry_group)

    @GeometryView("3D", duration_guess=1)
    def visualize_tunnel_structure(self, params, **kwargs):
        """"create a SCIA model and views its structure as a 3D model"""
        scia_model = self.create_scia_model(params)
        geometry_group_structure = self.create_structure_visualization(params, scia_model)
        geometry_group_segment = self.create_visualization_geometries(params, opacity=0.2)
        for obj in geometry_group_segment.children:
            geometry_group_structure.add(obj)
        return GeometryResult(geometry_group_structure)

    @PDFView("PDF View", duration_guess=20)
    def execute_scia_analysis(self, params, **kwargs):
        """"perform an analysis using SCIA on a third-party worker"""
        scia_model = self.create_scia_model(params)
        input_file, xml_def_file = scia_model.generate_xml_input()
        scia_model = self.get_scia_input_esa()

        scia_analysis = SciaAnalysis(input_file=input_file, xml_def_file=xml_def_file, scia_model=scia_model,
                                     result_type=ResultType.ENGINEERING_REPORT, output_document='Report_1')
        scia_analysis.execute(timeout=600)
        engineering_report = scia_analysis.get_engineering_report(as_file=True)

        return PDFResult(file=engineering_report)

    def download_scia_input_esa(self, params, **kwargs):
        """"Download scia input esa file"""
        scia_input_esa = self.get_scia_input_esa()

        filename = "model.esa"
        return DownloadResult(scia_input_esa, filename)

    def download_scia_input_xml(self, params, **kwargs):
        """"Download scia input xml file"""
        scia_model = self.create_scia_model(params)
        input_xml, _ = scia_model.generate_xml_input()

        return DownloadResult(input_xml, 'test.xml')

    def download_scia_input_def(self, params, **kwargs):
        """"Download scia input def file."""
        m = SciaModel()
        _, input_def = m.generate_xml_input()
        return DownloadResult(input_def, 'viktor.xml.def')

    def get_scia_input_esa(self) -> BytesIO:
        """"Retrieves the model.esa file."""
        esa_path = Path(__file__).parent / 'scia' / 'model.esa'
        scia_input_esa = BytesIO()
        with open(esa_path, "rb") as esa_file:
            scia_input_esa.write(esa_file.read())
        return scia_input_esa

    @staticmethod
    def create_scia_model(params) -> SciaModel:
        """"Create SCIA model"""
        model = SciaModel()

        line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        length = line_string.length / params.step1.segments
        width = params.step2.width
        height = params.step2.height
        floor_thickness = params.step2.floor_thickness
        roof_thickness = params.step2.roof_thickness
        wall_thickness = params.step2.wall_thickness
        material = SciaMaterial(0, 'concrete_slab')

        # floor
        node_floor_1 = model.create_node('node_floor_1', 0, 0, floor_thickness / 2)
        node_floor_2 = model.create_node('node_floor_2', 0, length, floor_thickness / 2)
        node_floor_3 = model.create_node('node_floor_3', width, length, floor_thickness / 2)
        node_floor_4 = model.create_node('node_floor_4', width, 0, floor_thickness / 2)
        floor_nodes = [node_floor_1, node_floor_2, node_floor_3, node_floor_4]
        floor_plane = model.create_plane(floor_nodes, floor_thickness, name='floor slab', material=material)

        # roof
        node_roof_1 = model.create_node('node_roof_1', 0, 0, height - roof_thickness / 2)
        node_roof_2 = model.create_node('node_roof_2', 0, length, height - roof_thickness / 2)
        node_roof_3 = model.create_node('node_roof_3', width, length, height - roof_thickness / 2)
        node_roof_4 = model.create_node('node_roof_4', width, 0, height - roof_thickness / 2)
        roof_nodes = [node_roof_1, node_roof_2, node_roof_3, node_roof_4]
        roof_plane = model.create_plane(roof_nodes, roof_thickness, name='roof slab', material=material)

        # section walls
        sections_x = np.linspace(wall_thickness / 2, width - (wall_thickness / 2), params.step2.number_of_sections + 1)
        for section_id, pile_x in enumerate(sections_x):
            n_front_bottom = model.create_node(f'node_section_wall_{section_id}_f_b', pile_x, 0, floor_thickness / 2)
            n_front_top = model.create_node(f'node_section_wall_{section_id}_f_t', pile_x, 0,
                                            height - roof_thickness / 2)
            n_back_bottom = model.create_node(f'node_section_wall_{section_id}_b_b', pile_x, length,
                                              floor_thickness / 2)
            n_back_top = model.create_node(f'node_section_wall_{section_id}_b_t', pile_x, length,
                                           height - roof_thickness / 2)

            model.create_plane([n_front_bottom, n_back_bottom, n_back_top, n_front_top],
                               wall_thickness,
                               name=f'section_slab_{section_id}',
                               material=material
                               )

        # create the support
        subsoil = model.create_subsoil(name='subsoil', stiffness=params.step3.soil_stiffness)
        model.create_surface_support(floor_plane, subsoil)

        # create the load group
        lg = model.create_load_group('LG1', LoadGroup.LoadOption.VARIABLE, LoadGroup.RelationOption.STANDARD,
                                     LoadGroup.LoadTypeOption.CAT_G)

        # create the load case
        lc = model.create_variable_load_case('LC1', 'first load case', lg, LoadCase.VariableLoadType.STATIC,
                                             LoadCase.Specification.STANDARD, LoadCase.Duration.SHORT)

        # create the load combination
        load_cases = {
            lc: 1
        }

        model.create_load_combination('C1', LoadCombination.Type.ENVELOPE_SERVICEABILITY, load_cases)

        # create the load
        force = params.step3.roof_load
        force *= -1000  # in negative Z-direction and kN -> n
        model.create_surface_load('SF:1', lc, roof_plane, SurfaceLoad.Direction.Z, SurfaceLoad.Type.FORCE, force,
                                  SurfaceLoad.CSys.GLOBAL, SurfaceLoad.Location.LENGTH)

        return model

    @staticmethod
    def create_visualization_geometries(params, opacity=1.0):
        """The SCIA model is converted to VIKTOR geometry here"""
        geometry_group = Group([])
        line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        width = params.step2.width
        length = line_string.length / params.step1.segments
        height = params.step2.height
        floor_thickness = params.step2.floor_thickness
        roof_thickness = params.step2.roof_thickness
        wall_thickness = params.step2.wall_thickness

        slab_material = Material('slab', threejs_roughness=1, threejs_opacity=opacity)

        floor_points = [
            Point(0, 0),
            Point(0, length),
            Point(width, length),
            Point(width, 0),
            Point(0, 0)
        ]

        section_wall_points = [
            Point(0, 0),
            Point(0, height - floor_thickness - roof_thickness),
            Point(length, height - floor_thickness - roof_thickness),
            Point(length, 0),
            Point(0, 0)
        ]

        # floor
        floor_slab_obj = Extrusion(floor_points, Line(Point(0, 0, 0), Point(0, 0, floor_thickness)))
        floor_slab_obj.material = slab_material
        geometry_group.add(floor_slab_obj)

        # roof
        roof_slab_obj = Extrusion(
            floor_points,
            Line(Point(0, 0, height - roof_thickness), Point(0, 0, height))
        )
        roof_slab_obj.material = slab_material
        geometry_group.add(roof_slab_obj)

        # left wall
        wall_slab_left_obj = Extrusion(
            section_wall_points,
            Line(Point(0, 0, floor_thickness), Point(wall_thickness, 0, floor_thickness)),
            profile_rotation=90
        )
        wall_slab_left_obj.material = slab_material
        geometry_group.add(wall_slab_left_obj)

        # right wall
        wall_slab_right_obj = Extrusion(
            section_wall_points,
            Line(Point(width - wall_thickness, 0, floor_thickness), Point(width, 0, floor_thickness)),
            profile_rotation=90
        )
        wall_slab_right_obj.material = slab_material
        geometry_group.add(wall_slab_right_obj)

        # create all section walls
        sections_x = np.linspace(wall_thickness / 2, width - (wall_thickness / 2), params.step2.number_of_sections + 1)
        for section_x in sections_x[1:-1]:
            wall_slab_section_obj = Extrusion(
                section_wall_points,
                Line(
                    Point(section_x - wall_thickness / 2, 0, floor_thickness),
                    Point(section_x + wall_thickness / 2, 0, floor_thickness)
                ),
                profile_rotation=90
            )
            wall_slab_section_obj.material = slab_material
            geometry_group.add(wall_slab_section_obj)

        return geometry_group

    @staticmethod
    def create_structure_visualization(params, scia_model):
        geometry_group = Group([])
        line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        floor_thickness = params.step2.floor_thickness
        roof_thickness = params.step2.roof_thickness
        width = params.step2.width
        length = line_string.length / params.step1.segments
        height_nodes = params.step2.height - roof_thickness / 2
        wall_thickness = params.step2.wall_thickness

        slab_material = Material('slab', threejs_roughness=1)

        # Draw green spheres at every node
        for node in scia_model.nodes:
            node_obj = Sphere(Point(node.x, node.y, node.z), 0.5)
            node_obj.material = Material('node', color=Color(0, 255, 0))
            geometry_group.add(node_obj)

        # Draw lines for floor and roof
        for z in [floor_thickness / 2, height_nodes]:
            front = CircularExtrusion(0.2, Line(Point(0, 0, z), Point(width, 0, z)))
            front.material = slab_material
            geometry_group.add(front)

            right = CircularExtrusion(0.2, Line(Point(width, 0, z), Point(width, length, z)))
            right.material = slab_material
            geometry_group.add(right)

            back = CircularExtrusion(0.2, Line(Point(width, length, z), Point(0, length, z)))
            back.material = slab_material
            geometry_group.add(back)

            left = CircularExtrusion(0.2, Line(Point(0, length, z), Point(0, 0, z)))
            left.material = slab_material
            geometry_group.add(left)

        # Draw lines for all sections
        sections_x = np.linspace(wall_thickness / 2, width - (wall_thickness / 2), params.step2.number_of_sections + 1)
        for x in sections_x:
            front = CircularExtrusion(0.2, Line(Point(x, 0, floor_thickness / 2), Point(x, 0, height_nodes)))
            front.material = slab_material
            geometry_group.add(front)

            back = CircularExtrusion(0.2, Line(Point(x, length, floor_thickness / 2), Point(x, length, height_nodes)))
            back.material = slab_material
            geometry_group.add(back)

            bottom = CircularExtrusion(0.2, Line(Point(x, 0, floor_thickness / 2), Point(x, length, floor_thickness / 2)))
            bottom.material = slab_material
            geometry_group.add(bottom)

            top = CircularExtrusion(0.2, Line(Point(x, 0, height_nodes), Point(x, length, height_nodes)))
            top.material = slab_material
            geometry_group.add(top)

        return geometry_group




