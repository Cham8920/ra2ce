# -*- coding: utf-8 -*-
"""
Created on 26-7-2021

@author: F.C. de Groen, Deltares
"""

# external modules
from osgeo import gdal
import numpy as np
import time

# local modules
from .networks_utils import *


class Network:
    def __init__(self, config):
        self.config = config
        self.network_config = config['network']
        self.source = config['network']['source']
        self.save_shp = config['network']['save_shp']
        self.primary_files = config['network']['primary_file']
        self.diversion_files = config['network']['diversion_file']
        self.file_id = config['network']['file_id']
        self.snapping = config['network']['snapping_threshold']
        self.pruning = config['network']['pruning_threshold']
        self.name = config['project']['name']
        self.output_path = config['static'] / "output_graph"


    def network_shp(self, crs=4326):
        """Creates a (graph) network from a shapefile
        Args:
            name (string): name of the analysis given by user (will be part of the name of the output files)
            InputDict (dict): dictionairy with paths/input that is used to create the network
            crs (int): the EPSG number of the coordinate reference system that is used
            snapping (bool): True if snapping is required, False if not
            SnappingThreshold (int/float): threshold to reach another vertice to connect the edge to
            pruning (bool): True if pruning is required, False if not
            PruningThreshold (int/float): edges smaller than this length (threshold) are removed
        Returns:
            G (networkX graph): The resulting network graph
        """


        lines = self.read_merge_shp()
        logging.info("Function [read_merge_shp]: executed with {} {}".format(self.primary_files, self.diversion_files))
        aadt_names = None

        # Multilinestring to linestring
        # Check which of the lines are merged, also for the fid. The fid of the first line with a traffic count is taken.
        # The list of fid's is reduced by the fid's that are not anymore in the merged lines
        edges, lines_merged = merge_lines_shpfiles(lines, self.file_id, aadt_names, crs)
        logging.info("Function [merge_lines_shpfiles]: executed with properties {}".format(list(edges.columns)))

        edges, id_name = gdf_check_create_unique_ids(edges, self.file_id)

        if self.snapping is not None or self.pruning is not None:
            if self.snapping is not None:
                edges = snap_endpoints_lines(edges, self.snapping, id_name, tolerance=1e-7)
                logging.info("Function [snap_endpoints_lines]: executed with threshold = {}".format(self.snapping))

        # merge merged lines if there are any merged lines
        if not lines_merged.empty:
            # save the merged lines to a shapefile - CHECK if there are lines merged that should not be merged (e.g. main + secondary road)
            lines_merged.to_file(os.path.join(self.output_path, "{}_lines_that_merged.shp".format(self.name)))
            logging.info("Function [edges_to_shp]: saved at ".format(os.path.join(self.output_path, '{}_lines_that_merged'.format(self.name))))


        # Get the unique points at the end of lines and at intersections to create nodes
        nodes = create_nodes(edges, crs)
        logging.info("Function [create_nodes]: executed")

        if self.snapping is not None or self.pruning is not None:
            if self.snapping is not None:
                # merged lines may be updated when new nodes are created which makes a line cut in two
                edges = cut_lines(edges, nodes, id_name, tolerance=1e-4)
                nodes = create_nodes(edges, crs)
                logging.info("Function [cut_lines]: executed")

        # create tuples from the adjecent nodes and add as column in geodataframe
        edges_complex = join_nodes_edges(nodes, edges, id_name)
        edges_complex.crs = {'init': 'epsg:{}'.format(crs)}  # set the right CRS

        # Save geodataframe of the resulting network to
        edges_complex.to_pickle(
            os.path.join(self.output_path, '{}_gdf.pkl'.format(self.name)))
        logging.info("Saved network to pickle in ".format(os.path.join(self.output_path, '{}_gdf.pkl'.format(self.name))))

        # Create networkx graph from geodataframe
        graph_complex = graph_from_gdf(edges_complex, nodes)
        logging.info("Function [graph_from_gdf]: executing, with '{}_resulting_network.shp'".format(self.name))

        #exporting complex graph because simple graph is not needed.
        return graph_complex, edges_complex

    def read_merge_shp(self, crs_=4326):
        """Imports shapefile(s) and saves attributes in a pandas dataframe.

        Args:
            shapefileAnalyse (string or list of strings): absolute path(s) to the shapefile(s) that will be used for analysis
            shapefileDiversion (string or list of strings): absolute path(s) to the shapefile(s) that will be used to calculate alternative routes but is not analysed
            idName (string): the name of the Unique ID column
            crs_ (int): the EPSG number of the coordinate reference system that is used
        Returns:
            lines (list of shapely LineStrings): full list of linestrings
            properties (pandas dataframe): attributes of shapefile(s), in order of the linestrings in lines
        """

        # read shapefiles and add to list with path
        if isinstance(self.primary_files, str):
            shapefiles_analysis = [self.config['static'] / "network" / shp for shp in self.primary_files.split(',')]
        if isinstance(self.diversion_files, str):
            shapefiles_diversion = [self.config['static'] / "network" / shp for shp in self.diversion_files.split(',')]

        def read_file(file, analyse=1):
            """"Set analysis to 1 for main analysis and 0 for diversion network"""
            shp = gpd.read_file(file)
            shp['to_analyse'] = analyse
            return shp

        # concatenate all shapefile into one geodataframe and set analysis to 1 or 0 for diversions
        lines = [read_file(shp) for shp in shapefiles_analysis]
        if isinstance(self.diversion_files, str):
            [lines.append(read_file(shp, 0)) for shp in shapefiles_diversion]
        lines = pd.concat(lines)

        lines.crs = {'init': 'epsg:{}'.format(crs_)}

        # append the length of the road stretches
        lines['length'] = lines['geometry'].apply(lambda x: line_length(x))

        if lines['geometry'].apply(lambda row: isinstance(row, MultiLineString)).any():
            for line in lines.loc[lines['geometry'].apply(lambda row: isinstance(row, MultiLineString))].iterrows():
                if len(linemerge(line[1].geometry)) > 1:
                    warnings.warn("Edge with {} = {} is a MultiLineString, which cannot be merged to one line. Check this part.".format(
                            self.file_id, line[1][self.file_id]))

        print('Shapefile(s) loaded with attributes: {}.'.format(list(lines.columns.values)))  # fill in parameter names

        return lines

    def network_osm_pbf(self):
        """Creates a network from an OSM PBF file."""
        return

    def network_osm_download(self):
        """Creates a network from a polygon by downloading via the OSM API in the extent of the polygon.

        Arguments:
            *InputDict* (Path) with
            PathShp [string]: path to shapefile (polygon) used to download from OSMnx the roads in that polygon
            NetworkType [string]: one of the network types from OSM, e.g. drive, drive_service, walk, bike, all
            RoadTypes [string]: formatted like "motorway|primary", one or multiple road types from OSM (highway)
            undirected is True, unless specified as False
            simplify graph is True, unless specified as False
            save_shapes is False, unless you would like to save shapes of both graphs

        Returns:
            graph_simple (Graph) : Simplified graph (for use in the indirect analyses)
            graph_complex_edges (GeoDataFrame : Complex graph (for use in the direct analyses)
        """
        poly_dict = read_geojson(self.network_config['polygon'][0])  # It can only read in one geojson
        poly = geojson_to_shp(poly_dict)

        if not self.network_config['road_types']:
            # The user specified only the network type.
            graph_complex = osmnx.graph_from_polygon(polygon=poly, network_type=self.network_config['network']['network_type'],
                                                 simplify=False, retain_all=True)
        elif not self.network_config['network_type']:
            # The user specified only the road types.
            cf = ('["highway"~"{}"]'.format(self.network_config['road_types'].replace(',', '|')))
            graph_complex = osmnx.graph_from_polygon(polygon=poly, custom_filter=cf, simplify=False, retain_all=True)
        else:
            # The user specified the network type and road types.
            cf = ('["highway"~"{}"]'.format(self.network_config['road_types'].replace(',', '|')))
            graph_complex = osmnx.graph_from_polygon(polygon=poly, network_type=self.network_config['network_type'],
                                                 custom_filter=cf, simplify=False, retain_all=True)

        logging.info('graph downloaded from OSM with {:,} nodes and {:,} edges'.format(len(list(graph_complex.nodes())),
                                                                                       len(list(graph_complex.edges()))))

        # Create 'edges_complex', convert complex graph to geodataframe
        logging.info('Start converting the graph to a geodataframe')
        edges_complex, nodes = graph_to_gdf(graph_complex)

        # edges_simple, nodes_simple = graph_to_gdf(graph_simple)
        logging.info('Finished converting the graph to a geodataframe')

        # Create 'graph_simple'
        graph_simple = simplify_graph_count(graph_complex)
        graph_simple = graph_create_unique_ids(graph_simple)

        # If the user wants to use undirected graphs, turn into an undirected graph (default).
        if not self.network_config['directed']:
            if type(graph_simple) == nx.classes.multidigraph.MultiDiGraph:
                graph_simple = graph_simple.to_undirected()

        return graph_simple, edges_complex

    def add_od_nodes(self, graph):
        """Adds origins and destinations nodes from shapefiles to the graph."""
        from .origins_destinations import read_OD_files, create_OD_pairs, add_od_nodes

        name = 'origin_destination_table'

        # Add the origin/destination nodes to the network
        ods = read_OD_files(self.network_config['origins'], self.network_config['origins_names'],
                            self.network_config['destinations'], self.network_config['destinations_names'],
                            self.network_config['id_name_origin_destination'], 'epsg:4326')


        ods = create_OD_pairs(ods, graph)
        ods.crs = 'epsg:4326'  # TODO: decide if change CRS to flexible instead of just epsg:4326

        # Save the OD pairs (GeoDataFrame) as pickle
        ods.to_feather(self.config['static'] / 'output_graph' / (name + '.feather'), index=False)
        logging.info(f"Saved {name + '.feather'} in {self.config['static'] / 'output_graph'}.")

        # Save the OD pairs (GeoDataFrame) as shapefile
        if self.network_config['save_shp']:
            ods_path = self.config['static'] / 'output_graph' / (name + '.shp')
            ods.to_file(ods_path, index=False)
            logging.info(f"Saved {ods_path.stem} in {ods_path.resolve().parent}.")

        graph = add_od_nodes(graph, ods)

        return graph

    def save_network(self, to_save, name, types=['pickle']):
        """Saves a geodataframe or graph to output_path"""
        if type(to_save) == gpd.GeoDataFrame:
            # The file that needs to be saved is a geodataframe
            if 'pickle' in types:
                output_path_pickle = self.config['static'] / 'output_graph' / (name + '_network.feather')
                to_save.to_feather(output_path_pickle, index=False)
                logging.info(f"Saved {output_path_pickle.stem} in {output_path_pickle.resolve().parent}.")
            if 'shp' in types:
                output_path = self.config['static'] / 'output_graph' / (name + '_network.shp')
                to_save.to_file(output_path, index=False)
                logging.info(f"Saved {output_path.stem} in {output_path.resolve().parent}.")

        elif type(to_save) == nx.classes.multigraph.MultiGraph:
            # The file that needs to be saved is a graph
            if 'shp' in types:
                graph_to_shp(to_save, self.config['static'] / 'output_graph' / (name + '_edges.shp'),
                             self.config['static'] / 'output_graph' / (name + '_nodes.shp'))
                logging.info(f"Saved {name + '_edges.shp'} and {name + '_nodes.shp'} in {self.config['static'] / 'output_graph'}.")
            if 'pickle' in types:
                output_path_pickle = self.config['static'] / 'output_graph' / (name + '_graph.gpickle')
                nx.write_gpickle(to_save, output_path_pickle, protocol=4)
                logging.info(f"Saved {output_path_pickle.stem} in {output_path_pickle.resolve().parent}.")
        return output_path_pickle

    def create(self, config_analyses):
        """Function with the logic to call the right analyses."""
        # Save the 'base' network as gpickle and if the user requested, also as shapefile.
        to_save = ['pickle'] if not self.save_shp else ['pickle', 'shp']

        # For all graph and networks - check if it exists, otherwise, make the graph and/or network.
        base_graph_path = self.config['static'] / 'output_graph' / 'base_graph.gpickle'
        base_network_path = self.config['static'] / 'output_graph' / 'base_network.feather'
        if (base_graph_path.is_file()) and (base_network_path.is_file()):
            config_analyses['base_graph'] = base_graph_path
            config_analyses['base_network'] = base_network_path
            logging.info(f"Existing graph found: {base_graph_path}.")
            logging.info(f"Existing network found: {base_network_path}.")
        else:
            # Create the network from the network source
            if self.source == 'shapefile':
                logging.info('Start creating a network from the submitted shapefile.')
                base_graph, edge_gdf = self.network_shp()

            elif self.source == 'OSM PBF':
                logging.info('Start creating a network from an OSM PBF file.')
                roadTypes = self.network_config['road_types'].lower().replace(' ', ' ').split(',')
                base_graph, edge_gdf = self.network_osm_pbf()

            elif self.source == 'OSM download':
                logging.info('Start downloading a network from OSM.')
                base_graph, edge_gdf = self.network_osm_download()

            # Check if all geometries between nodes are there, if not, add them as a straight line.
            base_graph = add_missing_geoms_graph(base_graph, geom_name='geometry')

            # Save the graph and geodataframe
            config_analyses['base_graph'] = self.save_network(base_graph, 'base', types=to_save)
            config_analyses['base_network'] = self.save_network(edge_gdf, 'base', types=to_save)

        if (self.network_config['origins'] is not None) and (self.network_config['destinations'] is not None):
            od_graph_path = self.config['static'] / 'output_graph' / 'origins_destinations_graph.gpickle'
            if od_graph_path.is_file():
                config_analyses['origins_destinations_graph'] = od_graph_path
                logging.info(f"Existing graph found: {od_graph_path}.")
            else:
                # Origin and destination nodes should be added to the graph.
                if (base_graph_path.is_file()) or base_graph:
                    if base_graph_path.is_file():
                        base_graph = nx.read_gpickle(base_graph_path)
                    od_graph = self.add_od_nodes(base_graph)
                    config_analyses['origins_destinations_graph'] = self.save_network(od_graph, 'origins_destinations', types=to_save)

        if self.network_config['hazard_map'] is not None:
            # There is a hazard map or multiple hazard maps that should be intersected with the graph.
            # Overlay the hazard on the geodataframe as well (todo: combine with graph overlay if both need to be done?)
            base_graph_hazard_path = self.config['static'] / 'output_graph' / 'base_hazard_graph.gpickle'
            if base_graph_hazard_path.is_file():
                config_analyses['base_hazard_graph'] = base_graph_hazard_path
                logging.info(f"Existing graph found: {base_graph_hazard_path}.")
            else:
                if (base_graph_path.is_file()) or base_graph:
                    if base_graph_path.is_file():
                        base_graph = nx.read_gpickle(base_graph_path)
                    haz = Hazard(base_graph, self.network_config['hazard_map'], self.network_config['aggregate_wl'])
                    base_graph_hazard = haz.hazard_intersect()
                    config_analyses['base_hazard_graph'] = self.save_network(base_graph_hazard, 'base_hazard', types=to_save)
                else:
                    logging.warning("No base graph found to intersect the hazard with. Check your network.ini file.")

            od_graph_hazard_path = self.config['static'] / 'output_graph' / 'origins_destinations_hazard_graph.gpickle'
            if od_graph_hazard_path.is_file():
                config_analyses['origins_destinations_hazard_graph'] = od_graph_hazard_path
                logging.info(f"Existing graph found: {od_graph_hazard_path}.")
            else:
                if (od_graph_path.is_file()) or od_graph:
                    if od_graph_path.is_file():
                        od_graph = nx.read_gpickle(od_graph_path)
                    haz = Hazard(od_graph, self.network_config['hazard_map'], self.network_config['aggregate_wl'])
                    od_graph_hazard = haz.hazard_intersect()
                    config_analyses['origins_destinations_hazard_graph'] = self.save_network(od_graph_hazard,
                                                                                             'origins_destinations_hazard',
                                                                                             types=to_save)
                else:
                    logging.warning("No base graph found to intersect the hazard with. Check your network.ini file.")

        return config_analyses


class Hazard:
    def __init__(self, graph_gdf, list_hazard_files, aggregate_wl):
        self.list_hazard_files = list_hazard_files
        self.aggregate_wl = aggregate_wl
        if type(graph_gdf) == gpd.GeoDataFrame:
            self.gdf = graph_gdf
            self.g = None
        else:
            self.gdf = None
            self.g = graph_gdf

    def overlay_hazard_raster(self, hf):
        """Overlays the hazard raster over the road segments."""
        # TODO differentiate between graph and geodataframe input
        # Name the attribute name the name of the hazard file
        hazard_names = [f.stem for f in hf]

        # Check if the extent and resolution of the different hazard maps are the same.
        same_extent = check_hazard_extent_resolution(hf)
        if same_extent:
            extent = get_extent(gdal.Open(str(hf[0])))
            logging.info("The flood maps have the same extent. Flood maps used: {}".format(", ".join(hazard_names)))

        for i, hn in enumerate(hazard_names):
            src = gdal.Open(str(hf[i]))
            if not same_extent:
                extent = get_extent(src)
            raster_band = src.GetRasterBand(1)

            try:
                raster = raster_band.ReadAsArray()
                size_array = raster.shape
                logging.info("Getting water depth or surface water elevation values from {}".format(hn))
            except MemoryError as e:
                logging.warning(
                    "The raster is too large to read as a whole and will be sampled point by point. MemoryError: {}".format(
                        e))
                size_array = None
                nodatavalue = raster_band.GetNoDataValue()

            # check which road is overlapping with the flood and append the flood depth to the graph
            for u, v, k, edata in self.g.edges.data(keys=True):
                if 'geometry' in edata:
                    # check how long the road stretch is and make a point every other meter
                    nr_points = round(edata['length'])
                    if nr_points == 1:
                        coords_to_check = list(edata['geometry'].boundary)
                    else:
                        coords_to_check = [edata['geometry'].interpolate(i / float(nr_points - 1), normalized=True) for
                                           i in range(nr_points)]

                    x_objects = np.array([c.coords[0][0] for c in coords_to_check])
                    y_objects = np.array([c.coords[0][1] for c in coords_to_check])

                    if size_array:
                        # Fastest method but be aware of out of memory errors!
                        water_level = sample_raster_full(raster, x_objects, y_objects, size_array, extent)
                    else:
                        # Slower method but no issues with memory errors
                        water_level = sample_raster(raster_band, nodatavalue, x_objects, y_objects, extent['minX'], extent['pixelWidth'], extent['maxY'], extent['pixelHeight'])

                    if len(water_level) > 0:
                        if self.aggregate_wl == 'max':
                            self.g[u][v][k][hn] = water_level.max()
                        elif self.aggregate_wl == 'min':
                            self.g[u][v][k][hn] = water_level.min()
                        elif self.aggregate_wl == 'mean':
                            self.g[u][v][k][hn] = mean(water_level)
                        else:
                            logging.warning("No aggregation method is chosen ('max', 'min' or 'mean).")
                    else:
                        self.g[u][v][k][hn] = np.nan

    def overlay_hazard_shp(self, hf):
        """Overlays the hazard shapefile over the road segments."""
        #TODO differentiate between graph and geodataframe input

        # Shapefile
        gdf = gpd.read_file(hf)
        spatial_index = gdf.sindex

        for u, v, k, edata in self.g.edges.data(keys=True):
            if 'geometry' in edata:
                possible_matches_index = list(spatial_index.intersection(edata['geometry'].bounds))
                possible_matches = gdf.iloc[possible_matches_index]
                precise_matches = possible_matches[possible_matches.intersects(edata['geometry'])]
                # TODO REQUEST USER TO INPUT THE COLUMN NAME OF THE HAZARD COLUMN
                hn='TODO'
                if not precise_matches.empty:
                    if self.aggregate_wl == 'max':
                        self.g[u][v][k][hn] = precise_matches[hn].max()
                    if self.aggregate_wl == 'min':
                        self.g[u][v][k][hn] = precise_matches[hn].min()
                    if self.aggregate_wl == 'mean':
                        self.g[u][v][k][hn] = precise_matches[hn].mean()
                else:
                    self.g[u][v][k][hn] = 0
            else:
                self.g[u][v][k][hn] = 0
        return

    def join_hazard_table(self):
        """Joins a table with IDs and hazard information with the road segments with corresponding IDs."""
        # TODO differentiate between graph and geodataframe input
        return

    def hazard_intersect(self):
        hazards_tif = [haz for haz in self.list_hazard_files if haz.suffix == '.tif']
        hazards_shp = [haz for haz in self.list_hazard_files if haz.suffix == '.shp']
        hazards_table = [haz for haz in self.list_hazard_files if haz.suffix in ['.csv', '.json']]

        if len(hazards_tif) > 0:
            start = time.time()
            self.overlay_hazard_raster(hazards_tif)
            end = time.time()
            print(end - start)
        elif len(hazards_shp) > 0:
            self.overlay_hazard_shp(hazards_shp)
        elif len(hazards_table) > 0:
            self.join_hazard_table(hazards_table)

        return self.g


def check_hazard_extent_resolution(list_hazards):
    if len(list_hazards) == 1:
        return True
    check_hazard_extent = [gdal.Open(str(haz)).GetGeoTransform() for haz in list_hazards]
    if len(set(check_hazard_extent)) == 1:
        # All hazard have the exact same extents and resolution
        return True
    else:
        return False


def get_extent(dataset):
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    transform = dataset.GetGeoTransform()
    minx = transform[0]
    maxx = transform[0] + cols * transform[1] + rows * transform[2]

    miny = transform[3] + cols * transform[4] + rows * transform[5]
    maxy = transform[3]

    width = maxx - minx
    height = maxy - miny

    return {"minX": minx, "maxX": maxx, "minY": miny, "maxY": maxy, "cols": cols, "rows": rows,
            "width": width, "height": height, "pixelWidth": transform[1], "pixelHeight": transform[5]}


def sample_raster_full(raster, x_objects, y_objects, size_array, extent):
    index_x_objects = np.int64(np.floor((x_objects - extent['minX']) / extent['pixelWidth']))
    index_y_objects = np.int64(np.floor((y_objects - extent['maxY']) / extent['pixelHeight']))

    fltr = np.logical_and(index_x_objects < size_array[1], index_y_objects < size_array[0])
    index_x_objects = index_x_objects[fltr]
    index_y_objects = index_y_objects[fltr]

    water_level = raster[tuple([index_y_objects, index_x_objects])]
    return water_level


def find_cell(x_y_coord, ll_corner, x_y_res):
    return np.int64(np.floor((x_y_coord - ll_corner) / x_y_res))


def find_cell_array_y(y_coord, ul_corner, y_res):
    return np.int64(np.floor((ul_corner - y_coord) / y_res))


def sample_raster(raster_band, nodatavalue, x_obj, y_obj, ulx, xres, uly, yres):
    water_levels = list()
    for x, y in zip(x_obj, y_obj):
        index_x_objects = find_cell(x, ulx, xres)
        index_y_objects = find_cell_array_y(y, uly, -yres)

        try:
            # It's possible that a part of some of the polygons is outside of the hazard extent.
            value = raster_band.ReadAsArray(index_x_objects, index_y_objects, 1, 1)
            if value[0, 0] == nodatavalue:
                water_levels.append(0)
            else:
                water_levels.append(value[0, 0])
        except TypeError as e:
            # The polygon that is partially outside of the hazard extent is skipped.
            logging.info(e)
            water_levels.append(0)

    return np.array(water_levels)
