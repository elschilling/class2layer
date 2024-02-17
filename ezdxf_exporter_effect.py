#! /usr/bin/python3 -sP
# coding=utf-8
#
# Copyright (C) 2005,2007,2008 Aaron Spike, aaron@ekips.org
# Copyright (C) 2008,2010 Alvin Penner, penner@vaxxine.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""
This file effect script for Inkscape export DXF file with layers from groups containing 
class attributes starting with Ifc. It allows mapping layer name, color, lineweight and linetype
and saving export settings.
"""


import inkex
from inkex import (
    colors,
    bezier,
    Transform,
    Group,
    Layer,
    Use,
    PathElement,
    Rectangle,
    Line,
    Circle,
    Ellipse,
)

import ezdxf
from uuid import uuid4
import gi
import io
import os
import json

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

def get_insert_point(node, mat):
    if not isinstance(node, (PathElement, Rectangle, Line, Circle, Ellipse)):
            return
    path = node.path.to_superpath().transform(Transform(mat) @ node.transform)
    return [path[0][0][1][0], path[0][0][1][1]]

class EzDxfExporter(inkex.EffectExtension):

    class ExportWindow(Gtk.Window):
        def __init__(self, exporter):
            self.exporter = exporter
            super().__init__(title='EzDXF Exporter')
            self.connect('destroy', Gtk.main_quit)
            self.set_border_width(10)
            # Export toggle, IfcClass, LayerName, Color, Lineweight, Linetype
            self.liststore = Gtk.ListStore(bool, str, str, int, str, str)

            treeview = Gtk.TreeView(model=self.liststore)
            renderer_toggle = Gtk.CellRendererToggle()
            renderer_toggle.connect("toggled", self.on_cell_toggled)

            column_toggle = Gtk.TreeViewColumn("Export", renderer_toggle, active=0)
            treeview.append_column(column_toggle)

            renderer_ifc_class = Gtk.CellRendererText()
            column_text = Gtk.TreeViewColumn("IfcClass", renderer_ifc_class, text=1)
            treeview.append_column(column_text)

            renderer_layer_name = Gtk.CellRendererText()
            renderer_layer_name.set_property("editable", True)
            renderer_layer_name.connect("edited", self.on_combo_changed, 2)
            column_text = Gtk.TreeViewColumn("LayerName", renderer_layer_name, text=2)
            treeview.append_column(column_text)

            renderer_layer_color = Gtk.CellRendererText()
            renderer_layer_color.set_property("editable", True)
            renderer_layer_color.connect("edited", self.on_combo_changed, 3)
            column_text = Gtk.TreeViewColumn("Color", renderer_layer_color, text=3)
            treeview.append_column(column_text)

            lineweight_combo = Gtk.ComboBox.new_with_model(self.create_lineweight_model())
            lineweight_combo.set_entry_text_column(0)
            renderer_lineweight = Gtk.CellRendererCombo()
            renderer_lineweight.set_property("editable", True)
            renderer_lineweight.set_property("model", lineweight_combo.get_model())
            renderer_lineweight.set_property("text-column", 0)
            renderer_lineweight.connect("edited", self.on_combo_changed, 4)
            lineweight_column = Gtk.TreeViewColumn("Lineweight", renderer_lineweight, text=4)
            treeview.append_column(lineweight_column)

            linetype_combo = Gtk.ComboBoxText()
            linetypes = ['Continuous', 'Dashed', 'Dot']
            for linetype in linetypes:
                linetype_combo.append_text(linetype)
            renderer_linetype = Gtk.CellRendererCombo()
            renderer_linetype.set_property("editable", True)
            renderer_linetype.set_property("model", linetype_combo.get_model())
            renderer_linetype.set_property("text-column", 0)
            renderer_linetype.connect("edited", self.on_combo_changed, 5)
            linetype_column = Gtk.TreeViewColumn("Linetype", renderer_linetype, text=5)
            treeview.append_column(linetype_column)

            hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox.pack_start(treeview, True, True, 0)
            button = Gtk.Button.new_with_label('Export DXF')
            button.connect('clicked', self.on_click_export)
            export_button = Gtk.Button(label="Save Settings")
            export_button.connect("clicked", self.on_export_button_clicked)
            load_button = Gtk.Button(label="Load Settings")
            load_button.connect("clicked", self.on_load_button_clicked)
            button_box.pack_start(export_button, True, True, 0)
            button_box.pack_start(load_button, True, True, 0)
            hbox.pack_start(button_box, True, True, 0)
            hbox.pack_start(button, True, True, 0)
            self.add(hbox)

        def create_lineweight_model(self):
            lineweights = [
                ['0', 0], ['0.05', 5], ['0.09', 9], ['0.13', 13], ['0.15', 15], ['0.18', 18], ['0.20', 20], ['0.25', 25],
                ['0.30', 30], ['0.35', 35], ['0.40', 40], ['0.50', 50], ['0.53', 53], ['0.60', 60], ['0.70', 70], ['0.80', 80], ['0.90', 90],
                ['1.00', 100], ['1.06', 106], ['1.20', 120], ['1.40', 140], ['1.58', 158], ['2.00', 200], ['2.11', 211]]
            lineweight_model = Gtk.ListStore(str, int)
            for lineweight in lineweights:               
                lineweight_model.append(lineweight)
            return lineweight_model
        
        def on_combo_changed(self, widget, path, text, column):
            if column == 3:
                text = int(text)
            self.liststore[path][column] = text

        def on_linetype_changed(self, widget, path, text, column):
            self.liststore[path][column] = text

        def get_lineweight_integer_value(self, lineweight_str):
            for row in self.create_lineweight_model():
                if row[0] == lineweight_str:
                    return row[1]
            return None

        def get_lineweight_string_value(self, lineweight_int):
            for row in self.create_lineweight_model():
                if row[1] == lineweight_int:
                    return row[0]
            return None

        def color_entry_edited(self, widget, path, text):
            self.liststore[path][3] = int(text)

        def on_cell_toggled(self, widget, path):
            self.liststore[path][0] = not self.liststore[path][0]

        def on_click_export(self, button):
            self.exporter.export_options = []
            for row in self.liststore:
                if row[0]:
                    self.exporter.export_options.append({
                        "Export": row[0],
                        "IfcClass": row[1],
                        "LayerName": row[2],
                        "Color": row[3],
                        "Lineweight": self.get_lineweight_integer_value(row[4]),
                        "Linetype": row[5],
                    })
            dialog = Gtk.FileChooserDialog(
                title="Export DXF",
                transient_for=self,
                action=Gtk.FileChooserAction.SAVE,
            )
            dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
            dialog.set_current_folder(os.path.dirname(self.exporter.document_path()))
            dialog.set_current_name(os.path.splitext(os.path.basename(self.exporter.document_path()))[0] + '.dxf')
            dialog.set_do_overwrite_confirmation(True)

            filter_dxf = Gtk.FileFilter()
            filter_dxf.set_name("DXF files")
            filter_dxf.add_pattern("*.dxf")
            dialog.add_filter(filter_dxf)

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                filename = dialog.get_filename()
                if not filename.endswith('.dxf'):
                    filename += '.dxf'
                self.exporter.create_dxf()
                self.exporter.dxf.saveas(filename)
            elif response == Gtk.ResponseType.CANCEL:
                pass

            dialog.destroy()

        def on_export_button_clicked(self, button):
            dialog = Gtk.FileChooserDialog(
                title="Export Settings to JSON",
                transient_for=self,
                action=Gtk.FileChooserAction.SAVE,
            )
            dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
            dialog.set_current_folder(os.path.dirname(self.exporter.document_path()))
            dialog.set_current_name(os.path.splitext(os.path.basename(self.exporter.document_path()))[0] + '.json')
            dialog.set_do_overwrite_confirmation(True)

            filter_json = Gtk.FileFilter()
            filter_json.set_name("JSON files")
            filter_json.add_pattern("*.json")
            dialog.add_filter(filter_json)

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                filename = dialog.get_filename()
                if not filename.endswith('.json'):
                    filename += '.json'
                data = []
                for row in self.liststore:
                    data.append({
                        "Export": row[0],
                        "IfcClass": row[1],
                        "LayerName": row[2],
                        "Color": row[3],
                        "Lineweight": self.get_lineweight_integer_value(row[4]),
                        "Linetype": row[5],
                    })
                with open(filename, "w") as json_file:
                    json.dump(data, json_file, indent=4)
            elif response == Gtk.ResponseType.CANCEL:
                pass

            dialog.destroy()

        def on_load_button_clicked(self, button):
            dialog = Gtk.FileChooserDialog(
                title="Load JSON Settings",
                transient_for=self,
                action=Gtk.FileChooserAction.OPEN,
            )
            dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
            dialog.set_current_folder(os.path.dirname(self.exporter.document_path()))
            filter_json = Gtk.FileFilter()
            filter_json.set_name("JSON files")
            filter_json.add_pattern("*.json")
            dialog.add_filter(filter_json)

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                filename = dialog.get_filename()
                if not filename.endswith('.json'):
                    filename += '.json'
                with open(filename, "r") as json_file:
                    data = json.load(json_file)
                    self.liststore.clear()
                    for item in data:
                        self.liststore.append([item["Export"], item["IfcClass"], item["LayerName"], item["Color"], self.get_lineweight_string_value(item['Lineweight']), item['Linetype']])
            elif response == Gtk.ResponseType.CANCEL:
                pass

            dialog.destroy()

    def build_gui(self):
        window = self.ExportWindow(self)
        for layer in self.layer_list:       
            window.liststore.append([True, layer, 'A-'+layer[3:].upper(), 0, '0', 'Continuous'])
        window.show_all()
        Gtk.main()

    def class2layer(self):
        self.layer_list = []
        xpath_expr = "//*[contains(concat(' ', normalize-space(@class), ' '), ' Ifc')]"
        elements = self.svg.xpath(xpath_expr)
        for element in elements:
            classes = element.get('class').split()
            IfcClass = [string for string in classes if string.startswith('Ifc')][0]
            if IfcClass not in self.layer_list:
                layer = self.svg.add(Group(id=IfcClass))
                layer.set('inkscape:groupmode', 'layer')
                layer.set('inkscape:label', IfcClass)
                self.layer_list.append(IfcClass)
            else:
                layer = self.svg.getElementById(IfcClass)
            layer.add(element)

    def create_dxf_layers(self):
        for entry in self.export_options:
            self.dxf.layers.add(
                name=entry['LayerName'],
                color=entry['Color'],
                lineweight=entry['Lineweight'],
                linetype=entry['Linetype'],
            )

    def filter_svg(self):
        layers = []
        for layer in self.export_options:
            layers.append(layer['IfcClass'])
        root = self.document.getroot()
        ns = {'inkscape': 'http://www.inkscape.org/namespaces/inkscape'}
        groups = root.findall(".//{http://www.w3.org/2000/svg}g[@inkscape:label]", namespaces=ns)
        filtered_groups = [group for group in groups if group.get('{http://www.inkscape.org/namespaces/inkscape}label') in layers]
        for group in groups:
            if group not in filtered_groups:
                root.remove(group)
        return root

    def dxf_add(self, str):
        self.dxf.append(str.encode(self.options.char_encode))

    def dxf_line(self, block, csp, first_coord):
        """Draw a line in the DXF format"""
        line = block.add_line((csp[0][0], csp[0][1]),(csp[1][0], csp[1][1]))
        line.translate(-first_coord[0], -first_coord[1], 0)

    def process_shape(self, node, mat, block, insert_point):
        rgb = (0, 0, 0)
        style = node.style("stroke")
        if style is not None and isinstance(style, inkex.Color):
            rgb = style.to_rgb()
        hsl = colors.rgb_to_hsl(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        self.color = 7  # default is blac
        if hsl[2]:
            self.color = 1 + (int(6 * hsl[0] + 0.5) % 6)  # use 6 hues

        if not isinstance(node, (PathElement, Rectangle, Line, Circle, Ellipse)):
            return

        path = node.path.to_superpath().transform(Transform(mat) @ node.transform)

        for sub in path:
            for i in range(len(sub) - 1):
                s = sub[i]
                e = sub[i + 1]
                if (s[1] == s[2] and e[0] == e[1]):
                    self.dxf_line(block, [s[1], e[1]], insert_point)

    def process_clone(self, node):
        """Process a clone node, looking for internal paths"""
        trans = node.get("transform")
        x = node.get("x")
        y = node.get("y")
        mat = Transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        if trans:
            mat @= Transform(trans)
        if x:
            mat @= Transform([[1.0, 0.0, float(x)], [0.0, 1.0, 0.0]])
        if y:
            mat @= Transform([[1.0, 0.0, 0.0], [0.0, 1.0, float(y)]])
        # push transform
        if trans or x or y:
            self.groupmat.append(Transform(self.groupmat[-1]) @ mat)
        # get referenced node
        refid = node.get("xlink:href")
        refnode = self.svg.getElementById(refid[1:])
        if refnode is not None:
            if isinstance(refnode, Group):
                self.process_group(refnode)
            elif isinstance(refnode, Use):
                self.process_clone(refnode)
            else:
                self.process_shape(refnode, self.groupmat[-1])
        # pop transform
        if trans or x or y:
            self.groupmat.pop()

    def process_group(self, group):
        """Process group elements"""
        if isinstance(group, Layer):
            for entry in self.export_options:
                if entry['IfcClass'] == group.label:
                    self.layer = entry['LayerName']

        block_def = self.dxf.blocks.new(str(uuid4()))
        trans = group.get("transform")
        insert_point = []
        if trans:
            self.groupmat.append(Transform(self.groupmat[-1]) @ Transform(trans))
        for node in group:
            try:
                if isinstance(node, Group):
                    self.process_group(node)
                elif isinstance(node, Use):
                    self.process_clone(node)
                else:
                    if not insert_point:
                        insert_point = get_insert_point(node, self.groupmat[-1])                   
                    self.process_shape(node, self.groupmat[-1], block_def, insert_point)
            except RecursionError as e:
                raise inkex.AbortExtension(
                    (
                        'Too many nested groups. Please use the "Deep Ungroup" extension first.'
                    )
                ) from e  # pylint: disable=line-too-long
        if trans:
            self.groupmat.pop()
        if insert_point:
            self.msp.add_blockref(
                            name=block_def.name,
                            insert=insert_point,
                            dxfattribs={"layer": self.layer}
                            )

    def create_dxf(self):
        scale = self.svg.inkscape_scale
        self.groupmat = [
            [[scale, 0.0, 0.0], [0.0, -scale, self.svg.viewbox_height * scale]]
        ]
        self.dxf = ezdxf.new(setup=True)
        self.msp = self.dxf.modelspace()
        self.create_dxf_layers()
        export_svg = self.filter_svg()
        self.process_group(export_svg)

    def effect(self):
        self.class2layer()
        self.build_gui()
        
if __name__ == "__main__":
    EzDxfExporter().run()
