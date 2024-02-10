#!/usr/bin/env python

import inkex
from inkex import Group

def class2layer(svg):
    layer_list = []
    xpath_expr = "//*[contains(concat(' ', normalize-space(@class), ' '), ' Ifc')]"
    elements = svg.xpath(xpath_expr)
    for element in elements:
        classes = element.get('class').split()
        IfcClass = [string for string in classes if string.startswith('Ifc')][0]
        # inkex.utils.debug(IfcClass)
        if IfcClass not in layer_list:
            layer = svg.add(Group(id=IfcClass))
            layer.set('inkscape:groupmode', 'layer')
            layer.set('inkscape:label', IfcClass)
            layer_list.append(IfcClass)
        else:
            layer = svg.getElementById(IfcClass)
        layer.add(element)
        # inkex.utils.debug(IfcClass)
    return svg

class CreateLayersFromClasses(inkex.EffectExtension):
    def effect(self):
        self.svg = class2layer(self.svg)

if __name__ == '__main__':
    CreateLayersFromClasses().run()