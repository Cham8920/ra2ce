import logging

from ra2ce.analyses.direct.damage.damage_function_road_type_lane import (
    DamageFunctionByRoadTypeByLane,
)


class ManualDamageFunctions:
    """ "
    This class keeps an overview of the manual damage functions

    Default behaviour is to find, load and apply all available functions
    At 22 sept 2022: only implemented workflow for DamageFunction_by_RoadType_by_Lane
    """

    def __init__(self):
        self.available = (
            {}
        )  # keys = name of the available functions; values = paths to the folder
        self.loaded = []  # List of DamageFunction objects (or child classes

    def find_damage_functions(self, folder) -> None:
        """Find all available damage functions in the specified folder"""
        assert folder.exists(), "Folder {} does not contain damage functions".format(
            folder
        )
        for subfolder in folder.iterdir():  # Subfolders contain the damage curves
            if subfolder.is_dir():
                # print(subfolder.stem,subfolder)
                self.available[subfolder.stem] = subfolder
        logging.info(
            "Found {} manual damage curves: \n {}".format(
                len(self.available.keys()), list(self.available.keys())
            )
        )
        return None

    def load_damage_functions(self):
        """ "Load damage functions in Ra2Ce"""
        for name, dir in self.available.items():
            damage_function = DamageFunctionByRoadTypeByLane(name=name)
            damage_function.from_input_folder(dir)
            damage_function.set_prefix()
            self.loaded.append(damage_function)
            logging.info(
                "Damage function '{}' loaded from folder {}".format(
                    damage_function.name, dir
                )
            )
# class DamageFWhateverFactoryBuilder:
#     available_items: Dict[str, Path]
#
#     def __init__(self):
#         self.available_items = {}
#
#     def build(self) -> Union[List[DamageFunctionByRoadTypeByLane], None]:
#         if not available_items:
#             return None
#         _loaded = []
#         for name, dir in self.available_items.items():
#             damage_function = DamageFunctionByRoadTypeByLane(name=name)
#             damage_function.from_input_folder(dir)
#             damage_function.set_prefix()
#             _loaded.append(damage_function)
#             logging.info(
#                 "Damage function '{}' loaded from folder {}".format(
#                     damage_function.name, dir
#                 )
#             )
#         return _loaded