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

from viktor.core import ViktorController
from viktor.geometry import GeoPoint
from viktor.views import MapPoint
from viktor.views import MapPolyline
from viktor.views import MapResult
from viktor.views import MapView
from .parametrization import TunnelParametrization
from .tunnel_segment_helper_functions import create_segments_from_geo_polyline


class TunnelController(ViktorController):
    """Controller class which acts as interface for the Sample entity type."""
    label = "Tunnel"
    parametrization = TunnelParametrization
    viktor_convert_entity_field = True

    @MapView('Map', duration_guess=2)
    def visualize_tunnel(self, params, **kwargs) -> MapResult:
        """Set the map view on which the line can be drawn for the tunnel and segments are filled in"""
        segment_points = create_segments_from_geo_polyline(params.step1.geo_polyline, params.step1.segments)
        features = []
        for point in segment_points:
            features.append(MapPoint.from_geo_point(GeoPoint.from_rd(point)))
        features.append(MapPolyline.from_geo_polyline(params.step1.geo_polyline))
        return MapResult(features)


        # if params.step1.geo_polyline:
        #     polyline = MapPolyline.from_geo_polyline(params.step1.geo_polyline)
        #     begin = np.array(RDWGSConverter.from_wgs_to_rd((polyline.points[0].lat, polyline.points[0].lon)))
        #     end = RDWGSConverter.from_wgs_to_rd((polyline.points[1].lat, polyline.points[1].lon))
        #     direction = end - begin
        #     # distance = np.linalg.norm(begin - end)
        #     current_point = begin
        #     color_cycle = cycle([
        #         viktor.Color.viktor_black(),
        #         viktor.Color.viktor_blue(),
        #         viktor.Color.viktor_yellow()
        #     ])
        #     for segment in range(params.step1.segments):
        #         next_point = current_point + (direction / params.step1.segments)
        #         print(next_point)
        #         current_point_wgs = RDWGSConverter.from_rd_to_wgs((current_point[0], current_point[1]))
        #         next_point_wgs = RDWGSConverter.from_rd_to_wgs((next_point[0], next_point[1]))
        #         points = [
        #             MapPoint(current_point_wgs[0], current_point_wgs[1]),
        #             MapPoint(next_point_wgs[0], next_point_wgs[1])
        #         ]
        #         line = MapPolyline(*points, color=next(color_cycle))
        #         features.append(line)
        #         current_point = next_point