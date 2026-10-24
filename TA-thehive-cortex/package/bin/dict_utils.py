# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

"""Pruning and truncating the JSON the modular inputs emit.

Split out of `common` (#24).
"""

# Standard library imports
from typing import Union


class Utils:

    def __init__(self, logger_file=None):
        # Initialize all settings to None
        self.logger_file = logger_file

        # Check the python version
        self.logger_file.debug(id="U1", message="Utils class initiated")

    def remove_unwanted_keys_from_dict(self, d: dict, l: list) -> dict:
        """This method is used to remove unwanted keys provided through a list 'l' from a dictionnary 'd'.
        Processing is taking into account the path within the dictionnary so it could be nested dictionnaries.
        Examples:
        - key1.key2.*.key3
        - key4.key5
        - key6

        Note: Wildcard is used for list of items

        Args:
            d (dict): input dictionnary
            l (list): list containing the keys to remove

        Returns:
            dict: the processed dictionnary 'd' with the list 'l'
        """
        self.logger_file.debug(
            id="U5",
            message=f"Event before processing (remove_unwanted_keys_from_dict): {d}",
        )
        new_d = d.copy()
        for path in l:
            new_d = self._remove_key_from_dict(d=new_d, path=path.split("."))
        self.logger_file.debug(
            id="U10",
            message=f"Event after processing (remove_unwanted_keys_from_dict): {new_d}",
        )
        return new_d

    def _remove_key_from_dict(
        self, d: Union[dict, list], path: list
    ) -> Union[dict, list]:
        """This method is used to remove one key from a dictionnary by giving the path to it

        Args:
            d (dict): input dictionnary
            path (list): path to the key in the dictionnary

        Returns:
            dict: dictionnary without the key if it exists.
        """
        new_d = d.copy()
        new_path = path.copy()
        key = new_path.pop(0)

        # Check if d is a dict or a list
        if isinstance(d, dict):
            # If the path is a final node
            if len(path) == 1:
                key = path[0]
                if key in d.keys():
                    del new_d[key]
                return new_d
            else:
                # It's a string or a list
                if key in new_d.keys():
                    child_d = self._remove_key_from_dict(new_d[key], path=new_path)
                    new_d[key] = child_d
                # Anyway return the new dict, modified or not
                return new_d
        elif isinstance(d, list) and key == "*":
            # Process each item
            # Check if it's a list of dict
            if len(d) > 0 and isinstance(d[0], dict):
                # Process each subdict
                items = []
                for item in d:
                    items.append(self._remove_key_from_dict(d=item, path=new_path))
                return items
            else:
                # As it's not dictionnaries, keep it as it
                return d
        else:
            # Unknown type
            return new_d

    def check_and_reduce_values_size(self, d: any, max_size: int) -> any:
        """Parse a dictionnary 'd' and truncate any value which is exceeding the 'max_size' length

        Args:
            d (any): input dictionnary or any substructure of the dictionnary
            max_size (int): maximum size for a given value. Exceeding this limit will truncate the value to max_size (and convert it as a string)

        Returns:
            dict: dictionnary processed and with values not exceeding 'max_size'
        """
        new_d = None
        if isinstance(d, dict):
            new_d = d.copy()
            # Process the all dictionnary
            for key in d.keys():
                new_d[key] = self.check_and_reduce_values_size(
                    d=d[key], max_size=max_size
                )
            return new_d
        elif isinstance(d, list):
            # Process each item of the list
            items = []
            for item in d:
                items.append(
                    self.check_and_reduce_values_size(d=item, max_size=max_size)
                )
            return items
        else:
            # It's not a dict or a list, consider it as final node and check
            if len(str(d)) > max_size:
                new_d = str(d)[0:max_size] + "[trunc]"
            else:
                new_d = d

            return new_d
