# -*- coding: utf-8 -*-
"""
Created on 26-7-2021

@author: F.C. de Groen, Deltares
@author: M. Kwant, Deltares
"""

# external modules
import time
from osmnx.graph import graph_from_xml

# local modules
from .networks_utils import *


class Network:
    """Network in GeoDataFrame or NetworkX format.

    Networks can be created from shapefiles, OSM PBF files, can be downloaded from OSM online or can be loaded from
    feather or gpickle files. Origin-destination nodes can be added.

    Attributes:
        config: A dictionary with the configuration details on how to create and adjust the network.
    """

    def __init__(self, config):
        # General
        self.config = config
        self.name = config['project']['name']
        self.output_path = config['static'] / "output_graph"

        # Network
        self.directed = config['network']['directed']
        self.source = config['network']['source']
        self.primary_files = config['network']['primary_file']
        self.diversion_files = config['network']['diversion_file']
        self.file_id = config['network']['file_id']
        self.polygon_file = config['network']['polygon']
        self.network_type = config['network']['network_type']
        self.road_types = config['network']['road_types']
        self.save_shp = config['network']['save_shp']

        # Origins and destinations
        self.origins = config['origins_destinations']['origins']
        self.destinations = config['origins_destinations']['destinations']
        self.origins_names = config['origins_destinations']['origins_names']
        self.destinations_names = config['origins_destinations']['destinations_names']
        self.id_name_origin_destination = config['origins_destinations']['id_name_origin_destination']
        try:
            self.region = config['static'] / 'network' / config['origins_destinations']['region']
            self.region_var = config['origins_destinations']['region_var']
        except:
            self.region = None
            self.region_var = None

        # Hazard
        self.hazard_map = config['hazard']['hazard_map']
        self.aggregate_wl = config['hazard']['aggregate_wl']

        # Cleanup
        self.snapping = config['cleanup']['snapping_threshold']
        # self.pruning = config['cleanup']['pruning_threshold']  # NOT IMPLEMENTED CURRENTLY
        self.segmentation_length = config['cleanup']['segmentation_length']

        # files
        self.base_graph_path = config['files']['base_graph']
        self.base_network_path = config['files']['base_network']
        self.od_graph_path = config['files']['origins_destinations_graph']

    def network_shp(self, crs=4326):
        """Creates a (graph) network from a shapefile.

        Returns the same geometries for the network (GeoDataFrame) as for the graph (NetworkX graph), because
        it is assumed that the user wants to keep the same geometries as their shapefile input.

        Args:
            crs (int): the EPSG number of the coordinate reference system that is used

        Returns:
            graph_complex (NetworkX graph): The resulting graph.
            edges_complex (GeoDataFrame): The resulting network.
        """

        lines = self.read_merge_shp()
        logging.info("Function [read_merge_shp]: executed with {} {}".format(self.primary_files, self.diversion_files))
        aadt_names = None

        # Multilinestring to linestring
        # Check which of the lines are merged, also for the fid. The fid of the first line with a traffic count is taken.
        # The list of fid's is reduced by the fid's that are not anymore in the merged lines
        edges, lines_merged = merge_lines_automatic(lines, self.file_id, aadt_names, crs)
        logging.info("Function [merge_lines_shpfiles]: executed with properties {}".format(list(edges.columns)))

        edges, id_name = gdf_check_create_unique_ids(edges, self.file_id)

        if self.snapping is not None:
            edges = snap_endpoints_lines(edges, self.snapping, id_name, tolerance=1e-7)
            logging.info("Function [snap_endpoints_lines]: executed with threshold = {}".format(self.snapping))

        # merge merged lines if there are any merged lines
        if not lines_merged.empty:
            # save the merged lines to a shapefile - CHECK if there are lines merged that should not be merged (e.g. main + secondary road)
            lines_merged.to_file(os.path.join(self.output_path, "{}_lines_that_merged.shp".format(self.name)))
            logging.info("Function [edges_to_shp]: saved at {}".format(os.path.join(self.output_path, '{}_lines_that_merged'.format(self.name))))

        # Get the unique points at the end of lines and at intersections to create nodes
        nodes = create_nodes(edges, crs, self.config['cleanup']['ignore_intersections'])
        logging.info("Function [create_nodes]: executed")

        if self.snapping is not None:
            # merged lines may be updated when new nodes are created which makes a line cut in two
            edges = cut_lines(edges, nodes, id_name, tolerance=1e-4)
            nodes = create_nodes(edges, crs, self.config['cleanup']['ignore_intersections'])
            logging.info("Function [cut_lines]: executed")

        # create tuples from the adjecent nodes and add as column in geodataframe
        edges_complex = join_nodes_edges(nodes, edges, id_name)
        edges_complex.crs = crs  # set the right CRS

        # Create networkx graph from geodataframe
        graph_complex = graph_from_gdf(edges_complex, nodes, node_id='node_fid')
        logging.info("Function [graph_from_gdf]: executing, with '{}_resulting_network.shp'".format(self.name))

        if self.segmentation_length is not None:
            edges_complex = Segmentation(edges_complex, self.segmentation_length)
            edges_complex = edges_complex.apply_segmentation()
            if edges_complex.crs is None:  # The CRS might have dissapeared.
                edges_complex.crs = crs  # set the right CRS

        # Exporting complex graph because the shapefile should be kept the same as much as possible.
        return graph_complex, edges_complex

    def network_osm_pbf(self, crs=4326):
        """Creates a network from an OSM PBF file.

        Returns:
            G_simple (NetworkX graph): Simplified graph (for use in the indirect analyses).
            G_complex_edges (GeoDataFrame): Complex graph (for use in the direct analyses).
        """
        road_types = self.road_types.lower().replace(' ', ' ').split(',')

        input_path = self.config['static'] / "network"
        osm_convert_exe = self.config['root_path'] / "executables" / 'osmconvert64.exe'
        osm_filter_exe = self.config['root_path'] / "executables" / 'osmfilter.exe'
        assert osm_convert_exe.exists() and osm_filter_exe.exists()

        pbf_file = input_path / self.primary_files
        o5m_path = input_path / self.primary_files.replace('.pbf', '.o5m')
        o5m_filtered_path = input_path / self.primary_files.replace('.pbf', '_filtered.o5m')

        if o5m_filtered_path.exists():
            logging.info('filtered o5m path already exists: {}'.format(o5m_filtered_path))
        elif o5m_path.exists():
            filter_osm(osm_filter_exe, o5m_path, o5m_filtered_path, tags=road_types)
            logging.info('filtered o5m pbf, created: {}'.format(o5m_path))
        else:
            convert_osm(osm_convert_exe, pbf_file, o5m_path)
            filter_osm(osm_filter_exe, o5m_path, o5m_filtered_path, tags=road_types)
            logging.info('Converted and filtered osm.pbf to o5m, created: {}'.format(o5m_path))

        logging.info('Start reading graph from o5m...')
        graph_complex = graph_from_xml(o5m_filtered_path, bidirectional=False, simplify=False, retain_all=False)

        # Create 'graph_simple'
        graph_simple, graph_complex, link_tables = create_simplified_graph(graph_complex)

        # Create 'edges_complex', convert complex graph to geodataframe
        logging.info('Start converting the graph to a geodataframe')
        edges_complex, node_complex = graph_to_gdf(graph_complex)
        logging.info('Finished converting the graph to a geodataframe')

        # Save the link tables linking complex and simple IDs
        self.save_linking_tables(link_tables[0], link_tables[1])

        if self.segmentation_length is not None:
            edges_complex = Segmentation(edges_complex, self.segmentation_length)
            edges_complex = edges_complex.apply_segmentation()
            if edges_complex.crs is None:  # The CRS might have dissapeared.
                edges_complex.crs = crs  # set the right CRS

        return graph_simple, edges_complex

    def network_osm_download(self):
        """Creates a network from a polygon by downloading via the OSM API in the extent of the polygon.

        Returns:
            graph_simple (NetworkX graph): Simplified graph (for use in the indirect analyses).
            complex_edges (GeoDataFrame): Complex graph (for use in the direct analyses).
        """
        poly_dict = read_geojson(self.polygon_file[0])  # It can only read in one geojson
        poly = geojson_to_shp(poly_dict)

        if not self.road_types:
            # The user specified only the network type.
            graph_complex = osmnx.graph_from_polygon(polygon=poly, network_type=self.network_type,
                                                 simplify=False, retain_all=True)
        elif not self.network_type:
            # The user specified only the road types.
            cf = ('["highway"~"{}"]'.format(self.road_types.replace(',', '|')))
            graph_complex = osmnx.graph_from_polygon(polygon=poly, custom_filter=cf, simplify=False, retain_all=True)
        else:
            # The user specified the network type and road types.
            cf = ('["highway"~"{}"]'.format(self.road_types.replace(',', '|')))
            graph_complex = osmnx.graph_from_polygon(polygon=poly, network_type=self.network_type,
                                                 custom_filter=cf, simplify=False, retain_all=True)

        logging.info('graph downloaded from OSM with {:,} nodes and {:,} edges'.format(len(list(graph_complex.nodes())),
                                                                                       len(list(graph_complex.edges()))))

        # Create 'graph_simple'
        graph_simple, graph_complex, link_tables = create_simplified_graph(graph_complex)

        # Create 'edges_complex', convert complex graph to geodataframe
        logging.info('Start converting the graph to a geodataframe')
        edges_complex, node_complex = graph_to_gdf(graph_complex)
        logging.info('Finished converting the graph to a geodataframe')

        # Save the link tables linking complex and simple IDs
        self.save_linking_tables(link_tables[0], link_tables[1])

        # If the user wants to use undirected graphs, turn into an undirected graph (default).
        if not self.directed:
            if type(graph_simple) == nx.classes.multidigraph.MultiDiGraph:
                graph_simple = graph_simple.to_undirected()

        # No segmentation required, the non-simplified road segments from OSM are already small enough

        return graph_simple, edges_complex

    def add_od_nodes(self, graph):
        """Adds origins and destinations nodes from shapefiles to the graph."""
        from .origins_destinations import read_OD_files, create_OD_pairs, add_od_nodes

        name = 'origin_destination_table'

        # Add the origin/destination nodes to the network
        ods = read_OD_files(self.origins, self.origins_names,
                            self.destinations, self.destinations_names,
                            self.id_name_origin_destination, self.config['origins_destinations']['origin_count'],
                            'epsg:4326', self.region, self.region_var)

        ods = create_OD_pairs(ods, graph)
        ods.crs = 'epsg:4326'  # TODO: decide if change CRS to flexible instead of just epsg:4326

        # Save the OD pairs (GeoDataFrame) as pickle
        ods.to_feather(self.config['static'] / 'output_graph' / (name + '.feather'), index=False)
        logging.info(f"Saved {name + '.feather'} in {self.config['static'] / 'output_graph'}.")

        # Save the OD pairs (GeoDataFrame) as shapefile
        if self.save_shp:
            ods_path = self.config['static'] / 'output_graph' / (name + '.shp')
            ods.to_file(ods_path, index=False)
            logging.info(f"Saved {ods_path.stem} in {ods_path.resolve().parent}.")

        graph = add_od_nodes(graph, ods)

        return graph

    def generate_origins_from_raster(self):
        """Adds origins and destinations nodes from shapefiles to the graph."""
        from .origins_destinations import origins_from_raster
        
        out_fn = origins_from_raster(self.config['static'] / 'network', self.polygon_file, self.origins[0])

        return out_fn

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

        def read_file(file, crs, analyse=1):
            """"Set analysis to 1 for main analysis and 0 for diversion network"""
            shp = gpd.read_file(file)
            if shp.crs != crs:
                logging.error('Shape projection is epsg:{} - only projection epsg:{} is allowed. '
                          'Please reproject the input file - {}'.format(shp.crs, crs, file))
                sys.exit()
            shp['analyse'] = analyse
            return shp

        # concatenate all shapefile into one geodataframe and set analysis to 1 or 0 for diversions
        lines = [read_file(shp, crs_) for shp in shapefiles_analysis]
        if isinstance(self.diversion_files, str):
            [lines.append(read_file(shp, crs_, 0)) for shp in shapefiles_diversion]
        lines = pd.concat(lines)

        lines.crs = crs_

        # append the length of the road stretches
        lines['length'] = lines['geometry'].apply(lambda x: line_length(x))

        if lines['geometry'].apply(lambda row: isinstance(row, MultiLineString)).any():
            for line in lines.loc[lines['geometry'].apply(lambda row: isinstance(row, MultiLineString))].iterrows():
                if len(linemerge(line[1].geometry)) > 1:
                    logging.warning("Edge with {} = {} is a MultiLineString, which cannot be merged to one line. Check this part.".format(
                            self.file_id, line[1][self.file_id]))

        logging.info('Shapefile(s) loaded with attributes: {}.'.format(list(lines.columns.values)))  # fill in parameter names

        return lines

    def save_network(self, to_save, name, types=['pickle']):
        """Saves a geodataframe or graph to output_path
        TODO: add encoding to ini file to make output more flexible"""
        if type(to_save) == gpd.GeoDataFrame:
            # The file that needs to be saved is a geodataframe
            if 'pickle' in types:
                output_path_pickle = self.config['static'] / 'output_graph' / (name + '_network.feather')
                to_save.to_feather(output_path_pickle, index=False)
                logging.info(f"Saved {output_path_pickle.stem} in {output_path_pickle.resolve().parent}.")
            if 'shp' in types:
                output_path = self.config['static'] / 'output_graph' / (name + '_network.shp')
                to_save.to_file(output_path, index=False)  #, encoding='utf-8' -Removed the encoding type because this causes some shapefiles not to save.
                logging.info(f"Saved {output_path.stem} in {output_path.resolve().parent}.")
            return output_path_pickle

        elif type(to_save) == nx.classes.multigraph.MultiGraph or type(to_save) == nx.classes.multidigraph.MultiDiGraph:
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
        else:
            return None

    def save_linking_tables(self, simple_to_complex, complex_to_simple):
        # save lookup table if necessary
        import json
        with open(self.config['static'] / 'output_graph' / 'simple_to_complex.json', 'w') as fp:
            json.dump(simple_to_complex, fp)
            logging.info('saved (or overwrote) simple_to_complex.json')
        with open(self.config['static'] / 'output_graph' / 'complex_to_simple.json', 'w') as fp:
            json.dump(complex_to_simple, fp)
            logging.info('saved (or overwrote) complex_to_simple.json')

    def create(self):
        """Function with the logic to call the right analyses."""
        # Save the 'base' network as gpickle and if the user requested, also as shapefile.
        to_save = ['pickle'] if not self.save_shp else ['pickle', 'shp']
        od_graph = None
        base_graph = None
        network_gdf = None

        # For all graph and networks - check if it exists, otherwise, make the graph and/or network.
        if self.base_graph_path is None and self.base_network_path is None:
            # Create the network from the network source
            if self.source == 'shapefile':
                logging.info('Start creating a network from the submitted shapefile.')
                base_graph, network_gdf = self.network_shp()

            elif self.source == 'OSM PBF':
                logging.info('Start creating a network from an OSM PBF file.')

                base_graph, network_gdf = self.network_osm_pbf()

            elif self.source == 'OSM download':
                logging.info('Start downloading a network from OSM.')
                base_graph, network_gdf = self.network_osm_download()

            elif self.source == 'pickle':
                logging.info('Start importing a network from pickle')
                base_graph = nx.read_gpickle(self.config['static'] / 'network' / 'base_graph.gpickle')
                network_gdf = read_pickle_file(self.config['static'] / 'network' / 'base_network.p')

            if self.source != 'pickle' and self.source != 'shapefile':
                # Graph & Network from OSM download or OSM PBF
                # Check if all geometries between nodes are there, if not, add them as a straight line.
                base_graph = add_missing_geoms_graph(base_graph, geom_name='geometry')

                if all(['length' in e for u, v, e in base_graph.edges.data()]) and any(['maxspeed' in e for u, v, e in base_graph.edges.data()]):
                    # Add time weighing - Define and assign average speeds; or take the average speed from an existing CSV
                    path_avg_speed = self.config['static'] / 'output_graph' / 'avg_speed.csv'
                    if path_avg_speed.is_file():
                        avg_speeds = pd.read_csv(path_avg_speed)
                    else:
                        avg_speeds = calc_avg_speed(base_graph, 'highway', save_csv=True,
                                                    save_path=self.config['static'] / 'output_graph' / 'avg_speed.csv')
                    G = assign_avg_speed(base_graph, avg_speeds, 'highway')

                    # make a time value of seconds, length of road streches is in meters
                    for u, v, k, edata in G.edges.data(keys=True):
                        hours = (edata['length'] / 1000) / edata['avgspeed']
                        G[u][v][k]['time'] = hours * 3600

            # Save the graph and geodataframe
            self.config['files']['base_graph'] = self.save_network(base_graph, 'base', types=to_save)
            self.config['files']['base_network'] = self.save_network(network_gdf, 'base', types=to_save)
        else:
            if self.base_graph_path is not None:
                base_graph = nx.read_gpickle(self.config['files']['base_graph'])
            else:
                base_graph = None
            if self.base_network_path is not None:
                network_gdf = gpd.read_feather(self.config['files']['base_network'])
            else:
                network_gdf = None

        # create origins destinations graph
        if (self.origins is not None) and (self.destinations is not None) and self.od_graph_path is None:
            # reading the base graphs
            if (self.base_graph_path is not None) and (base_graph is not None):
                base_graph = nx.read_gpickle(self.base_graph_path)
            # adding OD nodes
            if self.origins[0].suffix == '.tif':
                self.origins[0] = self.generate_origins_from_raster()
            od_graph = self.add_od_nodes(base_graph)
            self.config['files']['origins_destinations_graph'] = self.save_network(od_graph, 'origins_destinations', types=to_save)

        return {'base_graph': base_graph, 'base_network':  network_gdf, 'origins_destinations_graph': od_graph}


class Hazard:
    """Class where the hazard overlay happens.

    Attributes:
        network: GeoDataFrame of the network.
        graphs: NetworkX graphs.
    """

    def __init__(self, network, graphs):
        self.config = network.config

        # graphs
        self.graphs = graphs

        # files
        self.base_graph_path = self.config['files']['base_graph']
        self.base_network_path = self.config['files']['base_network']
        self.od_graph_path = self.config['files']['origins_destinations_graph']
        self.list_hazard_files = self.config['hazard']['hazard_map']
        self.aggregate_wl = self.config['hazard']['aggregate_wl']

        # bookkeeping for the hazard map names
        self.hazard_name_table = self.create_hazard_name_table()

    def overlay_hazard_raster(self, hf, graph):
        """Overlays the hazard raster over the road segments.

        Args:

        Returns:

        """
        # Name the attribute name the name of the hazard file
        hazard_names = list(self.hazard_name_table['File name'])
        ra2ce_names = list(set([n[:-3] for n in self.hazard_name_table['RA2CE name']]))

        # Check if the extent and resolution of the different hazard maps are the same.
        same_extent = check_hazard_extent_resolution(hf)
        if same_extent:
            extent = get_extent(gdal.Open(str(hf[0])))
            logging.info("The flood maps have the same extent. Flood maps used: {}".format(", ".join(hazard_names)))

        for i, (hn, rn) in enumerate(zip(hazard_names, ra2ce_names)):
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

            # check which road is overlapping with the flood and append the flood depth to the graph or geodataframe
            if type(graph) != gpd.GeoDataFrame:
                for u, v, k, edata in graph.edges.data(keys=True):
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
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = np.nanmax(water_level)
                            elif self.aggregate_wl == 'min':
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = np.nanmin(water_level)
                            elif self.aggregate_wl == 'mean':
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = np.nanmean(water_level)
                            else:
                                logging.warning("No aggregation method ('aggregate_wl') is chosen - choose from 'max', 'min' or 'mean'.")
                        else:
                            graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = np.nan

                    else:
                        graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = np.nan

            if type(graph) == gpd.GeoDataFrame:
                # start = time.time()
                for idx in range(len(graph.index)):
                    # check how long the road stretch is and make a point every other meter
                    nr_points = round(line_length(graph.iloc[idx]['geometry']))
                    if nr_points == 1:
                        coords_to_check = list(graph.iloc[idx]['geometry'].boundary)
                    else:
                        coords_to_check = [graph.iloc[idx]['geometry'].interpolate(i / float(nr_points - 1), normalized=True) for
                                           i in range(nr_points)]

                    x_objects = np.array([c.coords[0][0] for c in coords_to_check])
                    y_objects = np.array([c.coords[0][1] for c in coords_to_check])

                    if size_array:
                        # Fastest method but be aware of out of memory errors!
                        water_level = sample_raster_full(raster, x_objects, y_objects, size_array, extent)
                    else:
                        # Slower method but no issues with memory errors
                        water_level = sample_raster(raster_band, nodatavalue, x_objects, y_objects, extent['minX'],
                                                    extent['pixelWidth'], extent['maxY'], extent['pixelHeight'])

                    if len(water_level) > 0:
                        water_level = np.where(water_level <= 0, np.nan, water_level)
                        number_nan = np.sum(np.isnan(water_level))
                        factor_flooded = (len(water_level) - number_nan) / len(water_level)

                        graph.loc[idx, rn + '_fr'] = factor_flooded
                        graph.loc[idx, rn + '_mi'] = np.nanmin(water_level)
                        graph.loc[idx, rn + '_ma'] = np.nanmax(water_level)
                        graph.loc[idx, rn + '_me'] = np.nanmean(water_level)
                    else:
                        graph.loc[idx, rn+'_'+self.aggregate_wl[:2]] = np.nan
                # end = time.time()
                # logging.info(f"Hazard raster intersect time points method: {str(round(end - start, 2))}s")

                ## OLD METHOD START ##
                # start = time.time()
                # hazard = str(hf[0])
                # from tqdm import tqdm
                # from rasterstats import zonal_stats
                # tqdm.pandas(desc=hn)
                # flood_stats = graph.geometry.progress_apply(lambda x: zonal_stats(x, hazard,
                #                                                                   all_touched=True,
                #                                                                   stats="count min max mean"))
                # graph[rn + '_co'] = [x[0]['count'] for x in flood_stats]
                # graph[rn + '_mi'] = [x[0]['min'] for x in flood_stats]
                # graph[rn + '_ma'] = [x[0]['max'] for x in flood_stats]
                # graph[rn + '_me'] = [x[0]['mean'] for x in flood_stats]
                # end = time.time()
                # logging.info(f"Hazard raster intersect time rasterstats method: {str(round(end - start, 2))}s")
                ## OLD METHOD END ##

        return graph

    def overlay_hazard_shp(self, hf, graph):
        """Overlays the hazard shapefile over the road segments.

        Args:

        Returns:

        """
        hazard_names = list(self.hazard_name_table['File name'])
        ra2ce_names = list(set([n[:-3] for n in self.hazard_name_table['RA2CE name']]))
        hfns = self.config['hazard']['hazard_field_name']

        for i, (hn, rn, hfn) in enumerate(zip(hazard_names, ra2ce_names, hfns)):
            gdf = gpd.read_file(str(hf[i]))
            spatial_index = gdf.sindex

            if type(graph) != gpd.GeoDataFrame:
                for u, v, k, edata in graph.edges.data(keys=True):
                    if 'geometry' in edata:
                        possible_matches_index = list(spatial_index.intersection(edata['geometry'].bounds))
                        possible_matches = gdf.iloc[possible_matches_index]
                        precise_matches = possible_matches[possible_matches.intersects(edata['geometry'])]

                        if not precise_matches.empty:
                            if self.aggregate_wl == 'max':
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = precise_matches[hfn].max()
                            if self.aggregate_wl == 'min':
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = precise_matches[hfn].min()
                            if self.aggregate_wl == 'mean':
                                graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = precise_matches[hfn].mean()
                        else:
                            graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = 0
                    else:
                        graph[u][v][k][rn+'_'+self.aggregate_wl[:2]] = 0

            if type(graph) == gpd.GeoDataFrame:
                # graph.sjoin(gdf, how="left")
                print("THE OPTION OF SPATIALLY INTERSECTING A HAZARD SHAPEFILE WITH GDF IS NOT IMPLEMENTED YET.")
                #TODO: add this option

        return graph

    def join_hazard_table(self, graph):
        """Joins a table with IDs and hazard information with the road segments with corresponding IDs.

        Args:

        Returns:

        """
        if type(graph) == gpd.GeoDataFrame:
            for haz in self.list_hazard_files:
                if haz.suffix in ['.csv']:
                    graph = self.join_table(graph, haz)
            return graph

        elif graph is not None and type(graph) != gpd.GeoDataFrame:
            gdf, gdf_nodes = graph_to_gdf(graph, save_nodes=True)
            for haz in self.list_hazard_files:
                if haz.suffix in ['.csv']:
                    gdf = self.join_table(gdf, haz)

            # TODO: Check if the graph is created again correctly.
            graph = graph_from_gdf(gdf, gdf_nodes)
            return graph

    def join_table(self, graph, hazard):
        df = pd.read_csv(hazard)
        df = df[self.config['hazard']['hazard_field_name']]
        graph = graph.merge(df,
                            how='left',
                            left_on=self.config['network']['file_id'],
                            right_on=self.config['hazard']['hazard_id'])

        graph.rename(columns={self.config['hazard']['hazard_field_name']: [n[:-3] for n in self.hazard_name_table['RA2CE name']][0]}, inplace=True)  # Check if this is the right name
        return graph

    def create_hazard_name_table(self):
        agg_types = ['maximum', 'minimum', 'average', 'fraction of network segment impacted by hazard']

        df = pd.DataFrame()
        df[['File name', 'Aggregation method']] = [(haz.stem, agg_type) for haz in self.list_hazard_files for agg_type in agg_types]
        if all(['RP' in haz.stem for haz in self.list_hazard_files]):
            # Return period hazard maps are used
            # TODO: now it is assumed that there is a flood event, this should be made flexible
            rps = [haz.stem.split('RP_')[-1].split('_')[0] for haz in self.list_hazard_files]
            df['RA2CE name'] = ['F_' + 'RP' + rp + '_' + agg_type[:2] for rp in rps for agg_type in agg_types]
        else:
            # Event hazard maps are used
            # TODO: now it is assumed that there is a flood event, this should be made flexible
            df['RA2CE name'] = ['F_' + 'EV' + str(i+1) + '_' + agg_type[:2] for i in range(len(self.list_hazard_files)) for agg_type in agg_types]
        df['Full path'] = [haz for haz in self.list_hazard_files for agg_type in agg_types]
        return df

    def hazard_intersect(self, graph):
        hazards_tif = [haz for haz in self.list_hazard_files if haz.suffix == '.tif']
        hazards_shp = [haz for haz in self.list_hazard_files if haz.suffix == '.shp']
        hazards_table = [haz for haz in self.list_hazard_files if haz.suffix in ['.csv', '.json']]

        if len(hazards_tif) > 0:
            start = time.time()
            graph = self.overlay_hazard_raster(hazards_tif, graph)
            end = time.time()
            logging.info(f"Hazard raster intersect time: {str(round(end - start, 2))}s")
            return graph

        elif len(hazards_shp) > 0:
            start = time.time()
            graph = self.overlay_hazard_shp(hazards_shp, graph)
            end = time.time()
            logging.info(f"Hazard shapefile intersect time: {str(round(end - start, 2))}s")
            return graph

        elif len(hazards_table) > 0:
            start = time.time()
            graph = self.join_hazard_table(hazards_table, graph)
            end = time.time()
            logging.info(f"Hazard table intersect time: {str(round(end - start, 2))}s")
            return graph

        else:
            logging.warning("No hazard files found.")
            return graph

    def od_hazard_intersect(self, graph):
        """Overlays the origin and destination locations with the hazard maps

        Args:

        Returns:

        """
        # Intersect the origin and destination nodes with the hazard map (now only geotiff possible)
        hf = [haz for haz in self.list_hazard_files if haz.suffix == '.tif']

        # Name the attribute name the name of the hazard file
        hazard_names = list(self.hazard_name_table['File name'])
        ra2ce_names = list(set([n[:-3] for n in self.hazard_name_table['RA2CE name']]))

        # Check if the extent and resolution of the different hazard maps are the same.
        same_extent = check_hazard_extent_resolution(hf)
        if same_extent:
            extent = get_extent(gdal.Open(str(hf[0])))
            logging.info("The flood maps have the same extent. Flood maps used: {}".format(", ".join(hazard_names)))

        for i, (hn, rn) in enumerate(zip(hazard_names, ra2ce_names)):
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
            od_nodes = [(n, ndata) for n, ndata in graph.nodes.data() if 'od_id' in ndata]
            od_ids = [n[0] for n in od_nodes]
            od_x = np.array([n[1]['geometry'].coords[0][0] for n in od_nodes])
            od_y = np.array([n[1]['geometry'].coords[0][1] for n in od_nodes])

            if size_array:
                # Fastest method but be aware of out of memory errors!
                water_level = sample_raster_full(raster, od_x, od_y, size_array, extent)
            else:
                # Slower method but no issues with memory errors
                water_level = sample_raster(raster_band, nodatavalue, od_x, od_y,
                                            extent['minX'], extent['pixelWidth'], extent['maxY'],
                                            extent['pixelHeight'])

            attribute_dict = {od: {rn+'_'+self.aggregate_wl[:2]: wl} for od, wl in zip(od_ids, water_level)}
            nx.set_node_attributes(graph, attribute_dict)

        return graph

    def point_hazard_intersect(self, gdf):
        """Overlays the origin and destination locations with the hazard maps

        Args:

        Returns:

        """
        # Intersect the origin and destination nodes with the hazard map (now only geotiff possible)
        hf = [haz for haz in self.list_hazard_files if haz.suffix == '.tif']

        # Name the attribute name the name of the hazard file
        hazard_names = list(self.hazard_name_table['File name'])
        ra2ce_names = list(set([n[:-3] for n in self.hazard_name_table['RA2CE name']]))

        # Check if the extent and resolution of the different hazard maps are the same.
        same_extent = check_hazard_extent_resolution(hf)
        if same_extent:
            extent = get_extent(gdal.Open(str(hf[0])))
            logging.info("The flood maps have the same extent. Flood maps used: {}".format(", ".join(hazard_names)))

        for i, (hn, rn) in enumerate(zip(hazard_names, ra2ce_names)):
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

            x = gdf.geometry.apply(lambda p: p.x)
            y = gdf.geometry.apply(lambda p: p.y)

            if size_array:
                # Fastest method but be aware of out of memory errors!
                water_level = sample_raster_full(raster, x, y, size_array, extent)
            else:
                # Slower method but no issues with memory errors
                water_level = sample_raster(raster_band, nodatavalue, x, y,
                                            extent['minX'], extent['pixelWidth'], extent['maxY'],
                                            extent['pixelHeight'])

            gdf[rn+'_'+self.aggregate_wl[:2]] = water_level

        return gdf

    def save_network(self, to_save, name, types=['pickle']):
        """Saves a geodataframe or graph to output_path

        Args:

        Returns:

        """
        if type(to_save) == gpd.GeoDataFrame:
            # The file that needs to be saved is a geodataframe
            if 'pickle' in types:
                output_path_pickle = self.config['static'] / 'output_graph' / (name + '.feather')
                to_save.to_feather(output_path_pickle, index=False)
                logging.info(f"Saved {output_path_pickle.stem} in {output_path_pickle.resolve().parent}.")
            if 'shp' in types:
                output_path = self.config['static'] / 'output_graph' / (name + '_network.shp')
                to_save.to_file(output_path, index=False)
                logging.info(f"Saved {output_path.stem} in {output_path.resolve().parent}.")
            return output_path_pickle

        elif type(to_save) == nx.classes.multigraph.MultiGraph:
            # The file that needs to be saved is a graph
            if 'shp' in types:
                graph_to_shp(to_save, self.config['static'] / 'output_graph' / (name + '_edges.shp'),
                             self.config['static'] / 'output_graph' / (name + '_nodes.shp'))
                logging.info(f"Saved {name + '_edges.shp'} and {name + '_nodes.shp'} in {self.config['static'] / 'output_graph'}.")
            if 'pickle' in types:
                output_path_pickle = self.config['static'] / 'output_graph' / (name + '.gpickle')
                nx.write_gpickle(to_save, output_path_pickle, protocol=4)
                logging.info(f"Saved {output_path_pickle.stem} in {output_path_pickle.resolve().parent}.")
            return output_path_pickle

        return None

    def create(self):
        """ creates the hazard overlay over a graph """
        to_save = ['pickle'] if not self.config['network']['save_shp'] else ['pickle', 'shp']

        if self.base_graph_path is None and self.od_graph_path is None:
            logging.warning("Either a base graph or od graph is missing to intersect the hazard with. "
                            "Check your network folder.")

        for input_graph in ['base_graph', 'base_network', 'origins_destinations_graph']:

            file_path = self.config['files'][input_graph]
            graph = self.graphs[input_graph]
            hazard_path = self.config['files'][input_graph+'_hazard']
            self.graphs[input_graph + '_hazard'] = None

            if hazard_path is None:
                if file_path is not None or graph is not None:
                    if graph is None and input_graph != 'base_network':
                        graph = nx.read_gpickle(file_path)
                    elif graph is None:
                        graph = gpd.read_feather(file_path)
                    base_graph_hazard = self.hazard_intersect(graph)

                    if input_graph == 'origins_destinations_graph':
                        # Overlay the origins and destinations with the hazard maps
                        self.graphs[input_graph + '_hazard'] = self.od_hazard_intersect(graph)

                    # save graph with hazard
                    if base_graph_hazard is not None:
                        self.graphs[input_graph + '_hazard'] = base_graph_hazard
                        self.config['files'][input_graph+'_hazard'] = self.save_network(base_graph_hazard, input_graph+'_hazard', types=to_save)

        # Save the hazard name bookkeeping table.
        self.hazard_name_table.to_excel(self.config['output'] / 'hazard_names.xlsx', index=False)

        if 'isolation' in self.config:
            locations = gpd.read_file(self.config['isolation']['locations'][0])
            locations['i_id'] = locations.index
            locations = self.point_hazard_intersect(locations)
            self.save_network(locations, 'locations_hazard')

        return self.graphs
