#!/usr/bin/env python

import inkex
from inkex import Group

global layer_list
global layer
layer_list = []

class CreateLayersFromClasses(inkex.EffectExtension):
    def effect(self):
        svg = self.svg
        for g in svg.xpath('//svg:g'):
            g_class = g.get('class')
            check_str = 'Ifc'
            if g_class:
                for class_name in g_class.split():
                    if check_str in class_name:
                        if class_name not in layer_list:
                            layer = svg.add(Group(id=class_name))
                            layer.set('inkscape:groupmode', 'layer')
                            layer.set('inkscape:label', class_name)                          
                            layer_list.append(class_name)
                        else:
                            layer = svg.getElementById(class_name)
                        layer.add(g)

if __name__ == '__main__':
    CreateLayersFromClasses().run()