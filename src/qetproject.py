#!/usr/bin/env python3
# encoding: utf-8

#---------|---------|---------|---------|---------|---------|---------|---------|
# Copyright (C) 2018 Raul Roda <raulroda@yahoo.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#---------|---------|---------|---------|---------|---------|---------|---------|
 

# Imports
import logging as log
import operator
import re
import xml.etree.ElementTree as etree  # python3-lxml
from collections import OrderedDict


class QETProject:
    """This class works with the XML source file of a QET Project.
    The list of terminals has dicts like:
        {uuid, block_name, terminal_name, terminal_pos, 
        terminal_xref, terminal_type, conductor_name, cable, cable_cond} 
    where:
      - uuid: identificador of the terminal in the QET xml file.
      - block_name: terminal block that belong the terminal.
      - terminal_name: comes from the diagram
      - terminal_xref: location calculated of the element.
      - terminal_pos: position. Specified in the plugin. For sorterin purposes.
      - terminal_type: STANDARD, GROUND, FUSE. For representing purposes.
      - cable_cond: name of the cable of the electric hose.
      - conductor_name: Name of the electric hose.
      - bridge: True/False for a bridge to next terminal
      - num_reserve: Config for entire terminal block. Num of reserve terminals
      - reserve_positions: Config for entire terminal block. List of 
            positions for the reserve terminals.
    
    The tags for every key have the form %_ (are specified above)
    """

    # class attributes
    QET_COL_ROW_SIZE = 25  # pixels offset for elements coord
    QET_BLOCK_TERMINAL_SIZE = 30  # pixels offset for elements coord



    def __init__(self, project_file, fromPage='', \
            toPage = '', searchImplicitsConnections = False):
        """class initializer. Parses the QET XML file.
        @param project_file: file of the QET project
        @param folio_reference_type: how to calc XRefs when recover project info:
           'A' auto. Same xref as configured in the QET diagram project.
           'D' default (%f-%l%c) i.e. 15-F4
        @param fromPage: first page in range to be processed
        @param toPage: last page in range to be processed
        @param searchImplicitsConnections: True for search implicit connections in TB creation"""

        # Defines namespaces if exists. When changes the project logo in QET appears ns
        # but are not defined in the head, like:  xmlns:ns0="ns0".
        # If namespaces are not defines, etree cannot parse the XML file.
        with open(project_file, 'r' ,encoding='utf8') as f:
            xml = f.read()
            ns = re.findall( '[\s<]{1}(\w+):', xml )  # namesapaces
        if ns:
            ns = [ x for x in dict.fromkeys(ns) if \
                    x.startswith('ns') or x.startswith('dc') or x.startswith('rdf')   ]  # delete duplicates, and filtar
            ns_def = ''
            for n in ns:
                ns_str = 'xmlns:{}="{}"'.format(n, n)
                this_ns = re.findall( ns_str, xml )  # if found, no add ns definition again
                if not this_ns:
                    ns_def += 'xmlns:{}="{}" '.format(n,n)
            if ns_def:
                xml = re.sub('>', ' ' + ns_def + '>', xml, 1)  #replaces first ocurrence
                with open(project_file, 'w' ,encoding='utf8') as f:
                    f.write(xml)

        self._qet_tree = etree.parse(project_file)
        self.qet_project_file = project_file
        self.qet_project = self._qet_tree.getroot()
        
        # determine xref format to use or default
        self.folio_reference_type = self.qet_project.find('.//newdiagrams'). \
                find('report').attrib['label']

        # XML version
        self.xml_version = self.qet_project.attrib['version']

        # pageOffset for folio numbers. 
        # From versión 0.8 ot Qelectrotech, this attribute doesn't exist.
        # folioSheetQuantity ==> offset table of contents
        if 'folioSheetQuantity' in self.qet_project.attrib:
            self.pageOffset = int (self.qet_project.attrib['folioSheetQuantity']) 
        else:
            log.info ("Atribute 'folioSheetQuantity' doesn't exist. Assuming 0")
            self.pageOffset = 0
            

        # general project info
        self._totalPages = len (self.qet_project.findall('.//diagram')) + \
                self.pageOffset

        # elements type of terminal
        self._terminalElements = self._getListOfElementsByType( 'terminal' )

        # finds all terminals. A list of dicts
        self._set_used_terminals()



    def _getListOfElementsByType(self, element_type):
        """Return a list of component in library(collection) that
        have 'link_type' as element_type parameter.

        @return [] list with el names of elements that
                   are terminal as 'like_type'"""

        ret = []  # return list

        for element in self.qet_project.find('collection').iter('element'):
            definition = element[0]
            if 'link_type' in definition.attrib:
                if definition.attrib['link_type'] == element_type:
                    ret.append(element.attrib['name'])

        return list(set(ret))  # remove duplicates


    def _getElementName (self, element):
        """Returns the name of a terminal element.
        The name comes from 'dynamic_text' section.
        If not exists, the name is specified in elementInformation/label or 
        elementInformation/formula. 
        return: name of terminal"""

        dt = element.find('dynamic_texts')
        if dt:
            for d in dt.findall('dynamic_elmt_text'):
                if d.attrib['text_from'] == 'ElementInfo':
                    return d.findtext('text')

        ## old version of QET XML diagram doesn't have dynamic text.
        label = formula = ''
        elinfos = element.find('elementInformations')
        if elinfos:
            for t in elinfos.findall('elementInformation'):
                if t.attrib['name'] == 'label':
                    label = t.text
                if t.attrib['name'] == 'formula':
                    formula = t.text
        
        if label == None:  # attrib returns None if empty.
            label = ''
        if formula == None:
            formula = ''

        return [label, formula][label == '']


    def _getElementMetadata (self, element):
        """Returns the metadata of the terminal element.
        All the info is Function field under 'elementInformation'
        return: {} with the content of every key"""

        meta = ''
        ret = {}
    
        ## Get meta string
        for t in element.find('elementInformations').findall('elementInformation'):
            if t.attrib['name'] == 'function':
                meta = t.text
                break
        
        ## Getting data
        foo  = re.search(r'%p(\d+)(%|$)', meta)  # %p
        ret['terminal_pos'] = foo.group(1) if foo else ''

        foo = re.search(r'%t([^%]*)(%|$)', meta)  # %t
        tp = ''
        if foo: tp = foo.group(1)
        ret['terminal_type'] = foo.group(1) if tp!='' else 'STANDARD'
    
        foo  = re.search(r'%h([^%]*)(%|$)', meta)  # %h. Conductor of a hose
        ret['hose'] = foo.group(1) if foo else ''

        foo  = re.search(r'%n([^%]*)(%|$)', meta)  # %n . Cable Hose
        ret['conductor'] = foo.group(1) if foo else ''
                
        foo  = re.search(r'%b([^%]*)(%|$)', meta)  # %b
        ret['bridge'] = foo.group(1) if foo else ''

        foo = re.search(r'%r(\d+)(%|$)', meta)  # %r
        tp = ''
        if foo: tp = foo.group(1)
        ret['num_reserve'] = foo.group(1) if tp != '' else 0

        foo = re.search(r'%z([^%]*)(%|$)', meta)  # %z
        ret['reserve_positions'] = foo.group(1) if foo else ''

        foo = re.search(r'%s(\d+)(%|$)', meta)  # %s (terminals per terminal block)
        tp = ''
        if foo: tp = foo.group(1)
        ret['size'] = foo.group(1) if tp != '' else QETProject.QET_BLOCK_TERMINAL_SIZE

        return ret


    def _isValidTerminal (self, element):
        """ An element is valid if type is 'terminal' and label is like 'X1:1'
        @param element:  element  (XML etree object)
        @return: True / False"""
        
        tmp = self._getElementName(element).strip()  #kk 
        if re.search(r'^(.+):(.+)$', self._getElementName(element).strip()):
            if 'type' in element.attrib:  # elements must have a 'type'
                for el in self._terminalElements:  # searching type
                    if re.search(el + '$', element.attrib['type']):
                        return True
        
        return False


    def _getCableNum(self, diagram, terminalId):
        """Return the cable number connected at 'terminalId' in the page 'diagram'
        @param diagram: diagram(page) XML etree object
        @param terminalId: text with the terminal Id
        @return: string whith cable  number"""

        ret = ''
        log.debug ("Getting cable number connected to terminal {} at page {}".format ( \
            terminalId, diagram.attrib['title']))
        for cable in diagram.find('conductors').findall('conductor'):
            for cable_terminal in \
                    [x for x in cable.attrib if x[:8] == 'terminal' ]:
                if cable.attrib[cable_terminal] == terminalId:
                    ret = cable.attrib['num']
        return ret

    
    def _getXRef(self, diagram, element, offset_x = 0, offset_y = 0):
        """Return a string with the xreference.

        The element is specified by 'element' at page 'diagam'.
        The page number incremented in one if there are a "index" page

        @param diagram: diagram(page) XML etree object
        @param element: element XML etree object
        @param offset_x: correction of the coord x.
               Useful for Xref for the terminal of an element
        @param offset_y: correction of the coord y
        @return: string like "p-rc" (page - rowLetter colNumber)"""
        ret = self.folio_reference_type

        # get coord
        element_x = int(float(element.attrib['x'])) + int(float(offset_x))
        element_y = int(float(element.attrib['y'])) + int(float(offset_y))
        row, col = self._getXRefByCoord (diagram, element_x, element_y)
        diagram_page = str(int(diagram.attrib['order']) + self.pageOffset)

        # Change tags to real value
        if '%f' in ret:
            ret = ret.replace('%f', diagram_page)
        if '%F' in ret:
            # %F could include extra tags
            folio_label = diagram.attrib['folio']
            if '%id' in folio_label:
                folio_label = folio_label.replace('%id', diagram_page)
            if '%total' in folio_label:
                folio_label = folio_label.replace('%total', str(self._totalPages))
            if '%autonum' in folio_label:
                folio_label = folio_label.replace('%autonum', diagram_page)
            ret = ret.replace('%F', folio_label)
        if '%M' in ret:
            ret = ret.replace('%M', self._getDiagramAttribute(diagram,'machine'))
        if '%LM' in ret:
            ret = ret.replace('%LM', self._getDiagramAttribute(diagram, 'locmach'))
        if '%l' in ret:
            ret = ret.replace('%l', row)
        if '%c' in ret:
            ret = ret.replace('%c', col)

        return ret


    def _getDiagramAttribute(self, diagram, sAttrib):
        """Returns the value of an attribut of the diagram.
        If does not exist returns ''

        @param diagram: diagram(page) XML etree object
        @param sAttrib: attribute name
         """
        if sAttrib in diagram:
            return diagram.attrib[sAttrib]
        else:
            return ''


    def _getXRefByCoord(self, diagram, x, y):
        """Return a string with the xreference for the coordinates at page 'diagam'
        The page number incremented in one if there are a "index" page

        @param diagram: diagram(page) XML etree object
        @param x,y: coordinates
        @return: string like "p-rc" (page - rowLetter colNumber)"""

        # get requiered data
        cols = int(diagram.attrib['cols'])
        col_size = int(diagram.attrib['colsize'])
        rows = int(diagram.attrib['rows'])
        row_size = int(diagram.attrib['rowsize'])
        element_x = int(x)
        element_y = int(y)
        rows_letters = [chr(x + 65) for x in range(rows)]

        log.debug( 'Cols: {}\tCol size: {}\tRow size: {}\tX position: {}\tY Position: {}'. \
                format (cols, col_size, row_size, element_x, element_y))

        row_letter = rows_letters[ int(
                (element_y - QETProject.QET_COL_ROW_SIZE) / row_size) - 1 + 1]
                # +1: cal calc. -1 index of lists start 0.
        column = str(int((element_x - QETProject.QET_COL_ROW_SIZE) / col_size) + 1)
        return (row_letter, column)



    def _get_used_terminals(self):
        return self.__used_terminals



    def _set_used_terminals(self):
        """Creates a list of all terminal elements used in the qet project.
        List where every element is a dict. See class info.
        Sorted by Block_name and terminal_pos
        """

        ret = []

        # first search for elements of type 'terminal' and its conductors.
        for diagram in self.qet_project.findall('diagram'):  # all diagrams
            for element in diagram.findall('.//element'):  # all elements in diagram
                el = {}

                if self._isValidTerminal(element):

                    terminalName = self._getElementName(element).strip()
                    meta_data = self._getElementMetadata (element)
                    
                    terminals = element.find('terminals').findall( 'terminal' )
                    terminalId = terminals[0].attrib['id']
                    cableNum = self._getCableNum(diagram, terminalId)
                    terminalId2 = terminals[1].attrib['id']
                    cableNum2 = self._getCableNum(diagram, terminalId2)
                    if cableNum == '': cableNum = cableNum2
                    
                    el['uuid'] = element.attrib['uuid']
                    el['block_name'] = terminalName.split(':')[0]
                    el['terminal_name'] = terminalName.split(':')[1]
                    el['terminal_xref'] = self._getXRef(diagram, element)
                    el['cable'] = cableNum
                    
                    el['terminal_pos'] = [ meta_data['terminal_pos'], el['terminal_name'] ][meta_data['terminal_pos']=='']
                    el['terminal_type'] = meta_data['terminal_type']
                    el['hose'] = meta_data['hose']
                    el['conductor'] = meta_data['conductor']
                    el['bridge'] = meta_data['bridge']
                    el['num_reserve'] = meta_data['num_reserve']
                    el['reserve_positions'] = meta_data['reserve_positions']
                    el['size'] = meta_data['size']
                if el: ret.append(el)
        
        # SQL = ORDER BY block_name DESC, terminal_pos ASC
        ret.sort(key=operator.itemgetter('terminal_pos'))
        ret.sort(key=operator.itemgetter('block_name'), reverse=True)

        #Renum. position field from 1 by one-to-one
        memo_tb = ''; i = 1
        for t in ret:
            if t['block_name'] != memo_tb:
                i=1
            t['terminal_pos'] = i
            memo_tb = t['block_name']
            i +=1

        self.__used_terminals = ret


    def get_max_tb_length(self):
        """
        Returns the lenth of terminal-block with more terminals
        """
        t = [ x['block_name'] for x in self.__used_terminals]
        ocurrences = [t.count(i) for i in t]
        return max(ocurrences)

    def update_terminals(self, data):
        """Changes the config of every terminal in the diagra. The changes made 
        in the plugin will be save in the 'elementInformation' of every
        terminal."""
        for diagram in self.qet_project.findall('diagram'):  # all diagrams(pages)
            for element in diagram.iter('element'):  # all elements in diagram
                dt = [x for x in data if x['uuid'] == element.attrib['uuid']]
                if dt:
                    found = False
                    # value = r'%p{}%t{}%h{}%n{}%b{}%r{}%z{}%s{}'.format(
                    #         dt[0]['terminal_pos'], \
                    #         dt[0]['terminal_type'], \
                    #         dt[0]['hose'], \
                    #         dt[0]['conductor'], \
                    #         dt[0]['bridge'], \
                    #         dt[0]['num_reserve'], \
                    #         dt[0]['reserve_positions'], \
                    #         dt[0]['size'] )
                    value = r'%p{}%t{}%h{}%n{}%b{}%'.format(
                            dt[0]['terminal_pos'], \
                            dt[0]['terminal_type'], \
                            dt[0]['hose'], \
                            dt[0]['conductor'], \
                            dt[0]['bridge'] )
                    for elinfo in element.iter('elementInformation'):
                        if elinfo.attrib['name'] == 'function':
                            elinfo.text = value
                            found = True
                    if not found:  # crete a new child
                        #~ print ('----------------------- {}'.format(element.attrib['uuid']))
                        father = element.find('elementInformations')
                        new = etree.SubElement(father, \
                                'elementInformation',
                                name="function", \
                                show="0")
                        new.text = value


    def save_tb(self, filename):
        self._qet_tree.write(filename)  #, pretty_print=True)


    def insert_tb(self, name, tb_node):
        """Inserts a xml node representing a terminal block,
        removing first the old element if exists
        @param name: name of the segment
        @param tb_node: xml tree of the terminal block.
        @return: none"""
        
        element_name_to_delete = 'TB_' + name + '.elmt'
        father = self.qet_project.find('collection').find('category')
        
        # remove the old element
        for element in father.iter('element'):  # all elements in the imported collection
            if element.attrib['name'] == element_name_to_delete:
                father.remove(element)

        # adding the element
        father.insert(0, tb_node)
    

    def _get_tb_names(self):
        """
        Get a list of the terminal-block names sorted
        """
        sort_key = [x['block_name'] for x in self.__used_terminals]
        return list(OrderedDict.fromkeys(sort_key)) 
  
    
    # properties
    terminals = property(_get_used_terminals)
    tb_names = property(_get_tb_names)
