class Tomark:

    def table(listOfDicts):
        """Loop through a list of dicts and return a markdown table as a multi-line string.

        listOfDicts -- A list of dictionaries, each dict is a row
        """
        markdowntable = ""
        # Make a string of all the keys in the first dict with pipes before after and between each key
        markdownheader = '| ' + ' | '.join(map(str, listOfDicts[0].keys())) + ' |'
        # Make a header separator line with dashes instead of key names
        markdownheaderseparator = '|-----' * len(listOfDicts[0].keys()) + '|'
        # Add the header row and separator to the table
        markdowntable += markdownheader + '\n'
        markdowntable += markdownheaderseparator + '\n'
        # Loop through the list of dictionaries outputting the rows
        for row in listOfDicts:
            markdownrow = ""
            for key, col in row.items():
                markdownrow += '| ' + str(col) + ' '
            markdowntable += markdownrow + '|' + '\n'
        return markdowntable
