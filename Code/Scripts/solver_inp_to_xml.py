import sys

'''
Script to perform a direct conversion from a solver.inp to svFSI.xml file
Author: Nick Dorn
Date: 2024-08-08

----- README ------
- booleans in the solver.inp files take multiple forms (true, 1, t) (false, 0, f). 
    in the xml files I have seen, they are true/false. For this conversion, all booleans have been set to 0/1, for consistency.
- there are some differences in the solvers/preconditioners between the INP and XML files. please ensure these are correct.
- some parameters may take different values in svFSI and svFSIplus, please ensure these are correct.

------ USAGE ------
python solver_inp_to_xml.py path/to/solver.inp path/to/svFSI.xml
'''

class SolverInpConverter():
    '''class to convert a solver.inp file to an svFSI.xml file'''

    def __init__(self, inp_file='svFSI.inp', xml_file='svFSI.xml'):
        '''
        initialize the converter object
        
        :param inp_file: path to the solver.inp file
        :param xml_file: path to the output svFSI.xml file'''

        self.inp_file = inp_file
        self.xml_file = xml_file
        self.data_root = None
        self.lines = []
        self.parsed_data = {}


    def parse_inp_file(self, inp_file):
        '''
        Parse an inp file and return a list of key, value, subattributes.
        '''

        # initialize the root of the data tree
        self.data_root = DataNode(key='svFSIFile', value='0.1', is_root=True)

        with open(self.inp_file, 'r') as f:
            self.lines = f.readlines()

        # parse the data and create data tree
        self.data_root.parse(self.lines)


    def convert_to_xml(self):
        '''
        Convert the parsed data to an xml file.
        '''
        # format the data tree to xml
        self.data_root.format_for_xml()

        with open(self.xml_file, 'w') as f:
            # write the xml header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')

            # write the formatted data tree to xml file
            for line in self.data_root.xmllist:
                f.write(line)
        

class DataNode():
    '''
    Class to handle nested data from an inp file.
    '''
    def __init__(self, key: str, value: str, level: int =0, is_root: bool=False, root=None):
        '''
        initialize the DataNode object

        :param key: the key of the data
        :param value: the 'value' of the data which comes after the colon in the inp file
        :param level: the level of the data in the nested structure
        :param is_root: true if this is root node
        :param root: the root DataNode of the data tree
        '''

        if key == 'LS type':
            # corner case, LS_type becomes LS
            self.key = 'LS'
        else:
            # add underscores for xml
            self.key = key.replace(' ', '_')
        
        # convert bools to 1/0
        if value in ['true', 't']:
            self.value = '1'
        elif value in ['false', 'f']:
            self.value = '0'
        else:
            self.value = value
        
        self.is_root = is_root
        self.level = level # level within the tree
        if is_root:
            self.root = self
        else:
            self.root = root
        
        self.lines_parsed = 0 # keep track of lines searched in the input file
        self.children = [] # list of children nodes
        self.xmllist = [] # list of xml formatted data

        # a map of keys to attributes for certain xml tags. 
        self.key_to_attr = {
            'svFSIFile': 'version',
            'Add_face': 'name',
            'Add_mesh': 'name',
            'Add_projection': 'name',
            'Add_equation': 'type',
            'Domain': 'id',
            'Viscosity': 'model',
            'Constitutive_model': 'type',
            'LS': 'type',
            'Linear_algebra': 'type',
            'Output': 'type',
            'Add_BC': 'name',
        }
    


    def parse(self, lines):
        '''
        parse the nested data from the inp file.

        :param lines: the remaining lines of the inp file
        '''
        for idx, line in enumerate(lines):
            # remove whitespace from the line
            line = line.strip()

            if line.startswith('#') or len(line) == 0:
                # update lines searched, but don't do parse teh data
                self.lines_parsed += 1
                continue

            if idx >= self.lines_parsed:
                # parse this line, it has not been read yet
                self.update_lines_parsed() # update index of parsed lines
                # print(line)
                if '{' in line:
                    # either we have multiline nested data or inline nested data
                    if '{' in line[-1]: # multiline nested data
                        # jump one level down and parse data
                        key, value = line.split(': ', 1)
                        value, _ = value.rsplit(' ')

                        # add data to tree
                        curr_node = DataNode(key, value, level = self.level + 1, root=self.root)
                        curr_node.parent = self
                        self.children.append(curr_node)

                        # recursive step
                        curr_node.parse(lines[idx+1:])

                    else: # inline nested data
                        # parse node
                        node, subnode = line.split(' {')
                        node_key, node_value = node.split(': ', 1)
                        # parse nested data
                        subnode_key, subnode_value = subnode.split(': ', 1)
                        subnode_value = subnode_value.replace('}', '')

                        # add nodes to tree, we assume there is no further nesting so we will not take the recursive step
                        curr_node = DataNode(node_key, node_value, level = self.level + 1, root=self.root)
                        curr_node.parent = self
                        subnode = DataNode(subnode_key, subnode_value, level = self.level + 2, root=self.root)
                        subnode.parent = curr_node
                        curr_node.children.append(subnode)
                        self.children.append(curr_node)

                elif '}' in line:
                    # jump one level up in the tree
                    break

                else:
                    # no nesting, just add the data to children
                    key, value = line.split(': ', 1)
                    self.children.append(DataNode(key, value, level=self.level + 1, root=self.root))
                
            
    def update_lines_parsed(self, update_parent=True):
        '''
        recursively update lines parsed
        '''

        self.lines_parsed += 1

        if not self.is_root:
            self.parent.update_lines_parsed() # parent is also updated
    

    def format_for_xml(self):
        '''
        Format the data for xml
        '''

        if len(self.children) > 0:
            # add newline before if level 1
            if self.level == 1:
                self.xmllist.append('\n')
            # create xml wrapper
            if self.key in self.key_to_attr.keys():
                self.xmllist.append('\t' * (self.level - 1)+ f'<{self.key} {self.key_to_attr[self.key]}=\"{self.value}\" >\n')
            else:
                self.xmllist.append('\t' * (self.level - 1) + f'<{self.key}>\n')
            
            # beginning of the file requires a general simulation parameters tag
            if self.is_root:
                self.xmllist.extend(['\n', '<GeneralSimulationParameters>\n'])
            
            # create child xml's
            adding_gen_sim_params = True # this bool is to decide when to end the general simulation parameters tag
            for child in self.children:
                    if self.is_root:
                        # end general simulation parameters tag when we get to the multilevel parameters
                        if len(child.children) > 0:
                            # we are at the end of the general simulation parameters list
                            if adding_gen_sim_params:
                                self.xmllist.append('</GeneralSimulationParameters>\n')
                                adding_gen_sim_params = False
                
                   # recursive step for xml formatting
                    child.format_for_xml()

                    if type(child.xmllist) is list:
                        # extend the list
                        self.xmllist.extend(child.xmllist)
                    else:
                        # append to the list
                        self.xmllist.append(child.xmllist)

            # close xml wrapper
            self.xmllist.append('\t' * (self.level - 1) + f'</{self.key}>\n')

        else:
            # no children so we have an inline xml tag and will use a string
            self.xmllist = '\t' * (self.level - 1) + f'<{self.key}> {self.value} </{self.key}>\n'
                    

####### FOR TESTING AGAINST OTHER SVFSI.XML FILES #######
def compare_conversion(xml_file_conv, xml_file_ref):
    '''
    Compare converted and reference xml files to see if they are similar.

    :param xml_file_conv: path to converted xml file
    :param xml_file_ref: path to reference xml file
    '''

    # load in reference and converted xml files, ignorint blank lines
    with open(xml_file_ref, 'r') as f:
        xml_ref = [line.strip() for line in f.readlines() if line.strip()]
    with open(xml_file_conv, 'r') as f:
        xml_conv = [line.strip() for line in f.readlines() if line.strip()]
    
    # remove whitespace from the lines
    xml_conv = [line.replace(' ', '') for line in xml_conv]
    xml_ref = [line.replace(' ', '') for line in xml_ref]

    # fix bools in xml_ref for easier comparison
    for idx, line in enumerate(xml_ref):
        if 'true' in line:
            xml_ref[idx] = line.replace('true', '1')
        if 'false' in line:
            xml_ref[idx] = line.replace('false', '0')

    for idx, line in enumerate(xml_conv):
        if line != xml_ref[idx]:
            print(f'Conversion failed at line {idx}')
            print(f'CONVERTED: {line}')
            print(f'REFERENCE: {xml_ref[idx]}')

    if xml_conv == xml_ref:
        print('Conversion successful')

    # print(f'CONVERTED: {xml_conv}')
    # print(f'REFERENCE: {xml_ref}')

    '''
    note that the conversion will rarely be exactly the same as the reference file, 
    due to differences in the solvers, preconditioners and parameters between svFSI and svFSIplus'''
    

if __name__ == '__main__':

    inp_file = sys.argv[1]
    xml_file = sys.argv[2]

    # inp_file = 'Code/Scripts/svFSI.inp'
    # xml_file = 'Code/Scripts/svFSI_converted.xml'

    converter = SolverInpConverter(inp_file, xml_file)
    converter.parse_inp_file(inp_file)
    converter.convert_to_xml()

    # ref = 'tests/cases/fsi/pipe_3d/svFSI.xml'

    # compare_conversion(xml_file, ref)

    print(f'Conversion complete! Output written to {xml_file}')
    print('Please compare solver choice, preconditioner choice, booleans and parameters to svFSIplus documentation and a similar reference xml file to ensure correctness.')
    print('See script documentation for futher information')

