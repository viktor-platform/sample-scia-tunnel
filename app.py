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
from viktor.parametrization import DownloadButton
from viktor.parametrization import GeoPolylineField
from viktor.parametrization import LineBreak
from viktor.parametrization import NumberField
from viktor.parametrization import Parametrization
from viktor.parametrization import Step
from viktor.result import DownloadResult
from viktor.views import GeometryResult
from viktor.views import GeometryView
from viktor.views import MapPolygon
from viktor.views import MapPolyline
from viktor.views import MapResult
from viktor.views import MapView
from viktor.views import PDFResult
from viktor.views import PDFView


from viktor.parametrization import DownloadButton
from viktor.parametrization import GeoPolylineField
from viktor.parametrization import LineBreak
from viktor.parametrization import NumberField
from viktor.parametrization import Parametrization
from viktor.parametrization import Step

class TunnelParametrization(Parametrization):
    """Defines the input fields in left-side of the web UI in the Sample entity (Editor)."""
    step1 = Step('Select tunnel location', views='visualize_tunnel')
    step1.geo_polyline = GeoPolylineField('Location of tunnel')
    step1.segments = NumberField('Number of segments', default=5)

    step2 = Step('Define cross section', views='visualize_tunnel_segment')
    step2.width = NumberField('Total width', default=40, suffix='m')
    step2.height = NumberField('Total height', default=12, suffix='m')
    step2.number_of_sections = NumberField('Number of sections', default=2, step=0.1)
    step2.floor_thickness = NumberField('Floor thickness', default=1.5, suffix='m', step=0.1)
    step2.roof_thickness = NumberField('Roof thickness', default=2, suffix='m', step=0.1)
    step2.wall_thickness = NumberField('Wall thickness', default=1.2, suffix='m', step=0.1)

    step3 = Step('Create SCIA model', views='visualize_tunnel_structure')
    step3.roof_load = NumberField('Roof load', default=100, suffix='kN/m2')
    step3.soil_stiffness = NumberField('Soil stiffness', default=400, suffix='MN/m')
    step3.ln_break0 = LineBreak()
    step3.input_xml_btn = DownloadButton('viktor.xml', method='download_scia_input_xml')
    step3.input_def_btn = DownloadButton('viktor.xml.def', method='download_scia_input_def')
    step3.input_esa_btn = DownloadButton('model.esa', method='download_scia_input_esa')

    step4 = Step('Analyse engineering report', views='execute_scia_analysis')

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

        tunnel_line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        segment_length = tunnel_line_string.length / params.step1.segments
        for i in range(0, params.step1.segments):
            begin = i * segment_length
            end = (i + 1) * segment_length

            segment_line_string = substring(tunnel_line_string, begin, end)
            segment_left_line = segment_line_string.parallel_offset(params.step2.width, 'left')
            segment_right_line = segment_line_string.parallel_offset(params.step2.width, 'right')
            segment_linestring_coords = list(segment_left_line.coords) + list(segment_right_line.coords)

            segment_polygon = GeoPolygon(*[GeoPoint.from_rd(coordinate) for coordinate in segment_linestring_coords])
            features.append(MapPolygon.from_geo_polygon(segment_polygon))

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
        """ Perform an analysis using SCIA on a third-party worker and generate engineering report."""
        scia_model = self.create_scia_model(params)
        input_file, xml_def_file = scia_model.generate_xml_input()
        scia_model_esa = self.get_scia_input_esa()

        scia_analysis = SciaAnalysis(input_file=input_file, xml_def_file=xml_def_file, scia_model=scia_model_esa,
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

        return DownloadResult(input_xml, 'viktor.xml')

    def download_scia_input_def(self, params, **kwargs):
        """"Download scia input def file."""
        scia_model = SciaModel()
        _, input_def = scia_model.generate_xml_input()
        return DownloadResult(input_def, 'viktor.xml.def')

    def get_scia_input_esa(self) -> BytesIO:
        """Retrieves the model.esa file."""
        esa_path = Path(__file__).parent / 'scia' / 'model.esa'
        scia_input_esa = BytesIO()
        with open(esa_path, "rb") as esa_file:
            scia_input_esa.write(esa_file.read())
        return scia_input_esa

    @staticmethod
    def get_segment_length(params):
        """ Calculates the length of the tunnel segment."""
        line_string = LineString([pt.rd for pt in params.step1.geo_polyline.points])
        return line_string.length / params.step1.segments

    def create_scia_model(self, params) -> SciaModel:
        """ Create SCIA model"""
        scia_model = SciaModel()

        length = self.get_segment_length(params)
        width = params.step2.width
        height = params.step2.height
        floor_thickness = params.step2.floor_thickness
        roof_thickness = params.step2.roof_thickness
        wall_thickness = params.step2.wall_thickness
        material = SciaMaterial(0, 'concrete_slab')

        # floor
        node_floor_1 = scia_model.create_node('node_floor_1', 0, 0, floor_thickness / 2)
        node_floor_2 = scia_model.create_node('node_floor_2', 0, length, floor_thickness / 2)
        node_floor_3 = scia_model.create_node('node_floor_3', width, length, floor_thickness / 2)
        node_floor_4 = scia_model.create_node('node_floor_4', width, 0, floor_thickness / 2)
        floor_nodes = [node_floor_1, node_floor_2, node_floor_3, node_floor_4]
        floor_plane = scia_model.create_plane(floor_nodes, floor_thickness, name='floor slab', material=material)

        # roof
        node_roof_1 = scia_model.create_node('node_roof_1', 0, 0, height - roof_thickness / 2)
        node_roof_2 = scia_model.create_node('node_roof_2', 0, length, height - roof_thickness / 2)
        node_roof_3 = scia_model.create_node('node_roof_3', width, length, height - roof_thickness / 2)
        node_roof_4 = scia_model.create_node('node_roof_4', width, 0, height - roof_thickness / 2)
        roof_nodes = [node_roof_1, node_roof_2, node_roof_3, node_roof_4]
        roof_plane = scia_model.create_plane(roof_nodes, roof_thickness, name='roof slab', material=material)

        # section walls
        sections_x = np.linspace(wall_thickness / 2, width - (wall_thickness / 2), params.step2.number_of_sections + 1)
        for section_id, pile_x in enumerate(sections_x):
            n_front_bottom = scia_model.create_node(f'node_section_wall_{section_id}_f_b', pile_x, 0,
                                                    floor_thickness / 2)
            n_front_top = scia_model.create_node(f'node_section_wall_{section_id}_f_t', pile_x, 0,
                                                 height - roof_thickness / 2)
            n_back_bottom = scia_model.create_node(f'node_section_wall_{section_id}_b_b', pile_x, length,
                                                   floor_thickness / 2)
            n_back_top = scia_model.create_node(f'node_section_wall_{section_id}_b_t', pile_x, length,
                                                height - roof_thickness / 2)

            scia_model.create_plane([n_front_bottom, n_back_bottom, n_back_top, n_front_top],
                                    wall_thickness,
                                    name=f'section_slab_{section_id}',
                                    material=material
                                    )

        # create the support
        subsoil = scia_model.create_subsoil(name='subsoil', stiffness=params.step3.soil_stiffness * 1e06)
        scia_model.create_surface_support(floor_plane, subsoil)

        # create the load group
        load_group = scia_model.create_load_group('LG1', LoadGroup.LoadOption.VARIABLE,
                                                  LoadGroup.RelationOption.STANDARD, LoadGroup.LoadTypeOption.CAT_G)

        # create the load case
        load_case = scia_model.create_variable_load_case('LC1', 'first load case', load_group,
                                                         LoadCase.VariableLoadType.STATIC,
                                                         LoadCase.Specification.STANDARD, LoadCase.Duration.SHORT)

        # create the load combination
        load_cases = {
            load_case: 1
        }

        scia_model.create_load_combination('C1', LoadCombination.Type.ENVELOPE_SERVICEABILITY, load_cases)

        # create the load
        force = params.step3.roof_load
        force *= -1000  # in negative Z-direction and kN -> n
        scia_model.create_surface_load('SF:1', load_case, roof_plane, SurfaceLoad.Direction.Z, SurfaceLoad.Type.FORCE,
                                       force, SurfaceLoad.CSys.GLOBAL, SurfaceLoad.Location.LENGTH)

        return scia_model

    def create_visualization_geometries(self, params, opacity=1.0):
        """Creates a visualization of the tunnel"""
        geometry_group = Group([])
        length = self.get_segment_length(params)
        width = params.step2.width
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

    def create_structure_visualization(self, params, scia_model):
        """ Creates the visualization of the structure of how it will look in scia."""
        geometry_group = Group([])
        length = self.get_segment_length(params)
        floor_thickness = params.step2.floor_thickness
        roof_thickness = params.step2.roof_thickness
        width = params.step2.width
        height_nodes = params.step2.height - roof_thickness / 2
        wall_thickness = params.step2.wall_thickness

        slab_material = Material('slab', threejs_roughness=1)

        # Draw green spheres at every node
        for node in scia_model.nodes:
            node_obj = Sphere(Point(node.x, node.y, node.z), 0.5)
            node_obj.material = Material('node', color=Color(0, 255, 0))
            geometry_group.add(node_obj)

        # Draw lines for floor and roof
        for z_axis in [floor_thickness / 2, height_nodes]:
            front = CircularExtrusion(0.2, Line(Point(0, 0, z_axis), Point(width, 0, z_axis)))
            front.material = slab_material
            geometry_group.add(front)

            right = CircularExtrusion(0.2, Line(Point(width, 0, z_axis), Point(width, length, z_axis)))
            right.material = slab_material
            geometry_group.add(right)

            back = CircularExtrusion(0.2, Line(Point(width, length, z_axis), Point(0, length, z_axis)))
            back.material = slab_material
            geometry_group.add(back)

            left = CircularExtrusion(0.2, Line(Point(0, length, z_axis), Point(0, 0, z_axis)))
            left.material = slab_material
            geometry_group.add(left)

        # Draw lines for all sections
        sections_x = np.linspace(wall_thickness / 2, width - (wall_thickness / 2), params.step2.number_of_sections + 1)
        for x_axis in sections_x:
            front = CircularExtrusion(0.2, Line(Point(x_axis, 0, floor_thickness / 2), Point(x_axis, 0, height_nodes)))
            front.material = slab_material
            geometry_group.add(front)

            back = CircularExtrusion(0.2,
                                     Line(Point(x_axis, length, floor_thickness / 2),
                                          Point(x_axis, length, height_nodes)))
            back.material = slab_material
            geometry_group.add(back)

            bottom = CircularExtrusion(0.2, Line(Point(x_axis, 0, floor_thickness / 2),
                                                 Point(x_axis, length, floor_thickness / 2)))
            bottom.material = slab_material
            geometry_group.add(bottom)

            top = CircularExtrusion(0.2, Line(Point(x_axis, 0, height_nodes), Point(x_axis, length, height_nodes)))
            top.material = slab_material
            geometry_group.add(top)

        return geometry_group
