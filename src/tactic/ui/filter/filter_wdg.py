###########################################################
#
# Copyright (c) 2005, Southpaw Technology
#                     All Rights Reserved
#
# PROPRIETARY INFORMATION.  This software is proprietary to
# Southpaw Technology, and is not to be reproduced, transmitted,
# or disclosed in any way without written permission.
#
#

__all__ = ['BaseFilterWdg', 'GeneralFilterWdg', 'HierarchicalFilterWdg', 'SObjectSearchFilterWdg', 'SubmissionFilterWdg', 'SnapshotFilterWdg', 'WorkHourFilterWdg', 'NotificationLogFilterWdg', 'ShotFilterWdg' ]

import re
from pyasm.common import Environment, Common, SetupException, Date, TacticException, TimeCode
from pyasm.search import SearchType, Search, SObject, Sql, SearchInputException, SqlException, DbContainer, SearchException
from pyasm.biz import Schema, Project
from pyasm.web import Widget, DivWdg, HtmlElement, Table, SpanWdg, WebContainer
from pyasm.widget import HiddenWdg, TextWdg, PasswordWdg, SelectWdg, FilterSelectWdg, CheckboxWdg, HintWdg, CalendarInputWdg , TextAreaWdg

from tactic.ui.container import HorizLayoutWdg
from tactic.ui.common import BaseRefreshWdg
from tactic.ui.input import TextInputWdg

from filter_data import FilterData


class BaseFilterWdg(BaseRefreshWdg):
    '''Represents the base filter for use in SearchWdg'''

    def __init__(self, **kwargs):
        self.filter_mode = "and"
        self.visible = True
        # state passed from the SearchWdg
        self.state = {}

        self.num_filters_enabled = 0

        super(BaseFilterWdg, self).__init__(**kwargs)

    def is_visible(self):
        return self.visible

    def get_num_filters_enabled(self):
        return self.num_filters_enabled


    def alter_search(self, search):
        pass


    def set_filter_mode(self, filter_mode):
        assert filter_mode
        self.filter_mode = filter_mode

 
    def set_state(self, state):
        self.state = state

    def get_search_data_list(prefix, search_type=''):
        '''Get the search data for a particular prefix. For a more targeted list, a specific search type should be provided'''

        relevant_values_list = []
        values_list = FilterData.get().get_data()
        for i, values in enumerate(values_list):
            # hacky
            
            if not values.has_key("%s_column" % prefix):
                continue

            # filter out provided search_type
            item_search_type = values.get("%s_search_type" % prefix)
            if item_search_type and search_type != item_search_type:
                continue
            # check if this filter is enabled
            enabled = values.get("%s_enabled" % prefix)
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on', 'true'])
            if not is_enabled:
                pass
                #continue

            relevant_values_list.append(values)

        return relevant_values_list

    get_search_data_list = staticmethod(get_search_data_list)





class GeneralFilterWdg(BaseFilterWdg):
    '''Represents a very generic filter matching a column to a value'''

    def get_args_keys(self):
        return {
        'prefix': 'the prefix name for all of the input elements',
        'search_type': 'the search_type that this filter will operate on',
        'mode': 'sobject|parent|child|custom - these modes determine on which level the filter will do the search on',
        'columns': 'searchable columns override',

        'custom_filter_view': ' view for custom mode',
        }

    def init(self):
        self.prefix = self.kwargs.get('prefix')
        if not self.prefix:
            self.prefix = 'general'

        self.columns = []
        if self.kwargs.get('columns'):
            self.columns = self.kwargs.get('columns').split('|')
        if not self.columns:
            column_option =  self.options.get('columns')
            if column_option:
                self.columns = column_option.split('|')
        self.top_wdg = SpanWdg()

        self.search_type = self.kwargs['search_type']

        self.mode = self.kwargs.get('mode')
        if not self.mode:
            self.mode = 'sobject'

        assert self.mode in ['sobject', 'parent', 'child','custom','related', 'custom_related']

        schema = Schema.get()
        if self.mode in ['child','related']:
            self.related_types = []

            child_types = schema.get_child_types(self.search_type)
            related_types = schema.get_related_search_types(self.search_type)
            parent_type = schema.get_parent_type(self.search_type)

            remove_related = ['sthpw/clipboard','sthpw/sobject_list','sthpw/sobject_log','config/plugin_content','sthpw/connection']

            sthpw_types = []

            for related_type in related_types:
                if related_type in remove_related:
                    continue

                if related_type in self.related_types or \
                        related_type in sthpw_types:
                    continue

                if related_type.startswith("sthpw/"):
                    sthpw_types.append(related_type)
                else:
                    self.related_types.append(related_type)

            self.related_types.sort()
            sthpw_types.sort()
            self.related_types.extend(sthpw_types)

            for child_type in child_types:

                if child_type in remove_related:
                    continue

                if child_type in self.related_types:
                    continue
                self.related_types.append(child_type)
            if parent_type in self.related_types:
                self.related_types.remove(parent_type)






            self.related_types.insert(0, self.search_type)


        elif self.mode == 'parent':
            schema = Schema.get()
            parent_type = schema.get_parent_type(self.search_type)
            parent_search_type = self.kwargs.get("parent_search_type")
            if parent_search_type:
                parent_type = parent_search_type
            if parent_type == '*':
                project = Project.get()
                project_search_types = project.get_search_types()
                self.related_types = [x.get_value("search_type") for x in project_search_types]
            else:
                self.related_types = [parent_type]
        elif self.mode == 'custom_related':
            custom_related_types = self.kwargs.get("custom_related_search_types") or []
            if isinstance(custom_related_types, basestring):
                custom_related_types = custom_related_types.split(",")
            self.related_types = custom_related_types
        else:
            self.related_types = []

        self.related_types_column_dict = {}
        # verify the table represented by the search type exists and retrieve 
        # the column names for the column selector
        valid_related_types = []

        custom_related_stype_views = self.kwargs.get("custom_related_stype_views")

        for related_type in self.related_types:

            search_type_obj = SearchType.get(related_type, no_exception=True)
            if not search_type_obj:
                continue
            columns = []
            try:
                # the table may have been deleted from the db
                #columns = search_type_obj.get_columns(show_hidden=False)
                columns = SearchType.get_columns(related_type)
                columns = self.remove_columns(columns)
            except SqlException as e:
                DbContainer.abort_thread_sql()
                continue
            self.related_types_column_dict[related_type] = columns
            valid_related_types.append(related_type)
            

        self.related_types = valid_related_types

        self.search_type_indexes = {}
        for i, related_type in enumerate(self.related_types):
            self.search_type_indexes[related_type] = i


        self.config = None
        if self.mode == 'custom':
            view = self.kwargs.get('custom_filter_view')
            if not view:
                view = 'custom_filter'

            try:
                search = Search("config/widget_config")
                search.add_filter("search_type", self.search_type)
                search.add_filter("view", view)
                config_sobj = search.get_sobject()
            except SearchException as e:
                print("WARNING: ", e)
                config_sobj = None

            if config_sobj:
                config_xml = config_sobj.get_xml_value("config")
                from pyasm.widget import WidgetConfig, WidgetConfigView
                config = WidgetConfig.get(view=view, xml=config_xml)
                self.config = WidgetConfigView(self.search_type,view,[config])
                self.element_names = self.config.get_element_names()
                self.element_names.sort()
            else:
                self.element_names = []
                self.visible = False



    def get_default_display_handler(cls, element_name):
        return None
    get_default_display_handler = classmethod(get_default_display_handler)


    def get_default_display_wdg(cls, element_name, display_options, element_type):
        from type_filter_element_wdg import TypeFilterElementWdg
        filter = TypeFilterElementWdg(type=element_type)
        return filter
    get_default_display_wdg = classmethod(get_default_display_wdg)

 
    def set_columns(self, columns):
        self.columns = columns

    def set_columns_from_search_type(self, search_type):
        self.columns = SearchType.get_columns(search_type)
        self.columns = self.remove_columns(self.columns)


    def remove_columns(self, columns):
        columns2 = []

        remove = ['s_status']
        for column in columns:
            if column in remove:
                continue

            columns2.append(column)

        return columns2




    def get_display(self):

        if not self.columns:
            column_option =  self.options.get('columns')
            if column_option:
                self.columns = column_option.split('|')

            self.search_type = self.options.get("search_type")
            if not self.search_type:
                self.search_type = self.kwargs.get("search_type")

            if self.search_type:
                self.set_columns_from_search_type(self.search_type)


        # don't bother drawing if there is no parent
        if self.mode == 'parent':
            schema = Schema.get()
            parent_type = schema.get_parent_type(self.search_type)
            parent_search_type = self.kwargs.get("parent_search_type")
            if parent_search_type:
                parent_type = parent_search_type
            if not parent_type:
                widget = DivWdg()
                widget.add("<i>- No parent -</i>")
                widget.add_style("opacity: 0.3")
                widget.add_style("padding: 5px 50px 5px 50px")

                return widget


        if not self.columns:
            self.columns = []

        # contains everything
        top_wdg = self.top_wdg
        if self.kwargs.get("visible") == 'false': 
            top_wdg.add_style("visible: none") 
        top_wdg.set_id("%s_filter_top" % self.prefix )
        top_wdg.add_class("spt_filter_top")


     
        # add the hidden template filter
        dummy_div = DivWdg()
        dummy_div.add_style('display: none')
        op = 'and'
        level = 0
        i = -1
        filter_template = self._get_filter_wdg_with_op(i, op, level)
        dummy_div.add(filter_template)
        top_wdg.add(dummy_div)



        # add the container for all of the filters
        filter_container = DivWdg()
        filter_container.set_id("%s_filter_container" % self.prefix)
        filter_container.add_class("spt_filter_container")

        top_wdg.add(filter_container)



        # add the filters
        try:
            filter_data = FilterData.get()
            num_filters = 0
            for x in filter_data.get_data():
                if x.get('prefix') == self.prefix:
                    num_filters += 1
            if num_filters == 0:
                num_filters = 1
        except:
            num_filters = 1
        


        filter_mode = filter_data.get_values_by_index("filter_mode", 0)
        filter_mode = filter_mode.get('filter_mode')
        if filter_mode:
            self.filter_mode = filter_mode
        # set the default ops and levels
        if self.filter_mode == 'custom':
            search_ops = filter_data.get_values_by_index("search_ops", 0)
            ops = search_ops.get("ops")
            levels = search_ops.get("levels")
        else:
            ops = None
            levels = None

        if not ops:
            ops = ['and' for x in range(0,num_filters)]
        if not levels:
            levels = [0 for x in range(0,num_filters)]


        # add each filter item
        for i in range(0, num_filters):
            if i == 0:
                op = 'and'
                level = 0
            else:
                op = ops[i-1]
                level = levels[i-1]
            filter_wdg =  self._get_filter_wdg_with_op(i, op, level)
            filter_container.add(filter_wdg)



        # depending on the selection, the other ui changes
        types = ['string', 'integer', 'timestamp', 'login', 'expression', 'timecode','boolean']

        # provide a bunch alternatives of alternative filters based on the
        # attribute selection
        filter_types = DivWdg()
        filter_types.add_class("spt_filter_options")
        filter_types.add_style("display: none")


        if self.mode != 'custom':
            for type in types:
                filter_type = self.get_filter_type_wdg(type, -1)
                filter_types.add(filter_type)

        else:
            # add widgets from the config
            if self.config:
                #element_names = self.config.get_element_names()
                element_names = self.element_names
                for element_name in element_names:
                    filter_type_wdg = DivWdg()
                    filter_type_wdg.add_style("float: left")
                    filter_type_wdg.add_class("spt_filter_type_wdg")

                    filter = self.config.get_display_widget(element_name)
                    filter_type_wdg.add(filter)

                    filter_types.add(filter_type_wdg)

        top_wdg.add(filter_types)


        # create all of the selector filters
        #
        # provide a bunch alternatives of alternative column filters based on
        # the search type
        if self.mode in ["child","parent","related", "custom_related"]:
            column_types = SpanWdg()
            column_types.add_class("%s_filter_columns" % self.prefix)
            column_types.add_style("display: none")

            column_indexes = {}
            for related_type in self.related_types:
                columns = self.related_types_column_dict.get(related_type)

                filter_selector = self.get_column_selector(related_type, -1, columns=columns)
                column_types.add(filter_selector)

                child_column_indexes = self.get_column_indexes(related_type)

                column_indexes = dict(column_indexes.items() + child_column_indexes.items() )

            top_wdg.add(column_types)


        elif self.mode == "custom":
            # go through the custom elements and add these
            column_indexes = {}
            element_names = self.element_names
            for i, element_name in enumerate(element_names):
                column_indexes[str(element_name)] = i

        else:

            column_indexes = self.get_column_indexes(self.search_type)

        hidden = HiddenWdg("%s_column_indexes" % self.prefix, column_indexes )
        hidden.set_class("spt_filter_indexes")
        top_wdg.add(hidden)


        return top_wdg


    def get_column_types(self, search_type):
        '''maps the relationship between the type of the column and the filter
        index that is used to search.'''

        # process the column types to match indexes of the above elements
        search_type_obj = SearchType.get(search_type)
        column_types = search_type_obj.get_column_types()
        return column_types


    def get_column_indexes(self, search_type):
        '''maps the relationship between the type of the column and the filter
        index that is used to search.'''

        # process the column types to match indexes of the above elements
        column_types = SearchType.get_tactic_types(search_type)

        column_indexes = {}
        for column, type in column_types.items():
            type_index = 0
            if type in ["string", "varchar"]:
                type_index = 0
            elif type in ['integer', 'float', 'currency']:
                type_index = 1
            elif type in ['timestamp','date','time','datetime2']:
                type_index = 2
            elif type == 'login':
                type_index = 3
            elif type == 'timecode':
                type_index = 5
            elif type == 'boolean':
                type_index = 6
            else:
                type_index = 0

            column_indexes[column.encode('UTF-8')] = type_index

        # add the expression entry
        column_indexes["_expression"] = 4

        return column_indexes



    def _get_filter_wdg_with_op(self, i, op, level):

        incr = 20

        filter_container = DivWdg()
        if i == -1:
            filter_container.add_class("spt_filter_template_with_op")
        else:
            filter_container.add_class("spt_filter_container_with_op")


        if i != 0:
            spacing = DivWdg()
            spacing.add_class("spt_spacing")
            spacing.add_style("float: left")
            spacing.add_style("width: %spx" % (incr-level*incr))
            spacing.add_style("height: 3px")
            spacing.add("&nbsp;")
            filter_container.add(spacing)


            op_div = DivWdg()
            if i == -1:
                op_div.add_class("spt_op_template")
            else:
                op_div.add_class("spt_op")
            op_div.add_style("position: relative")
            op_div.add_style("padding: 1px 0 1px 0")
            op_div.add_class("hand")
            
            # add the op and level displays
            op_div.add_attr("spt_mode", self.mode)
            op_div.add_attr("spt_level", level)
            op_div.add_attr("spt_op", op)


            value_div = DivWdg()
            value_div.add_class("spt_op_display")
            value_div.add_attr("title", "Click to switch between 'and'/'or'.  Shift-Click to switch between logical levels")
            op_div.add(value_div)
            if self.filter_mode == 'custom':
                value_div.add(op)
            else:
                value_div.add('&nbsp;')

            if level == 1:
                value_div.add_color("background", "background")
                value_div.set_style("padding: 5px")
            else:
                value_div.set_style("padding: 1px")


            value_div.add_behavior( {
            'type': 'click_up',
            'cbjs_action': '''
            var search_top = bvr.src_el.getParent(".spt_search_filters");
            var filter_mode = search_top.getElement('.spt_search_filter_mode');
            if (filter_mode.value =='custom') {

                var top = bvr.src_el.getParent(".spt_filter_top");
                var elements = top.getElements(".spt_filter_container_with_op");

                var filter = bvr.src_el.getParent(".spt_filter_container_with_op");

                var element_groups = [];
                var index = 0;
                var element_group = [];
                var current_group = null;

                // organize all of the filters into groups
                for (var i = 0; i < elements.length; i++) {

                    var element_op = elements[i].getElement(".spt_op");
                    // if element_op does not exist, skip.  This occurs on the
                    // first one for now
                    if (element_op == null) {
                        continue;
                    }
                    var element_level = element_op.getAttribute("spt_level");
                    var element_op_value = element_op.getAttribute("spt_op");

                    if (element_level == "1") {
                        element_group = [];
                        element_groups.push(element_group);

                        element_group.push(elements[i]);
                        if (elements[i] == filter) {
                            current_group = element_group;
                        }

                        element_group = [];
                        element_groups.push(element_group);
                        continue;
                    }

                    element_group.push(elements[i]);

                    if (elements[i] == filter) {
                        current_group = element_group;
                    }
                }


                var value = bvr.src_el.innerHTML;
                for (var i = 0; i < current_group.length; i++) {
                    var filter = current_group[i];
                    var display = filter.getElement(".spt_op_display");
                    var op = filter.getElement(".spt_op");

                    if (value == 'and') {
                        display.innerHTML = 'or';
                        op.setAttribute("spt_op", 'or');
                    }
                    else {
                        display.innerHTML = 'and';
                        op.setAttribute("spt_op", 'and');
                    }

                }
            }
            '''
            } )

            # what is this DTS for?
            value_div.add_class("SPT_DTS")
            palette = value_div.get_palette()
            bg_color = palette.color("background")
            light_bg_color = palette.color("background", +10)

            value_div.add_behavior( {
            'type': 'click_up',
            'modkeys': 'SHIFT',
            'cbjs_action': '''
            var value = bvr.src_el.innerHTML;

            var search_top = bvr.src_el.getParent(".spt_search_filters");
            var filter_mode = search_top.getElement('.spt_search_filter_mode');
            if (filter_mode.value =='custom') {

                var top = bvr.src_el.getParent(".spt_filter_container_with_op");
                var display = top.getElement(".spt_op_display");
                var op = top.getElement(".spt_op");
                spacing = top.getElement(".spt_spacing");

                var level = op.getAttribute("spt_level");
                if (level == '1') {
                    op.setAttribute("spt_level", "0");
                    spacing.setStyle("width", "20px");
                    display.setStyle("background", "%s")
                    display.setStyle("padding", "1px")
                }
                else {
                    op.setAttribute("spt_level", "1");
                    spacing.setStyle("width", "2px");
                    display.setStyle("background", "%s")
                    display.setStyle("padding", "5px")
                }
            }
            '''%(bg_color, light_bg_color)
            } )

            filter_container.add(op_div)


        # add each filter item
        spacing = DivWdg()
        spacing.add_style("float: left")
        spacing.add_style("width: %spx" % (incr+5))
        spacing.add("&nbsp;")
        filter_container.add(spacing)

        filter_name = "filter_%s" % i
        filter = self.get_filter_wdg(filter_name, i)
        filter_container.add(filter)


        return filter_container



    def get_filter_wdg(self, filter_name, filter_index):
        '''gets the filter widget.  There are 2 parts to a filter.  A selection
        of the filter name (which often corresponds to the attribute of an
        sobject and the actual filter'''

        div = DivWdg()
        div.add_style("float: left")
        hidden = HiddenWdg("prefix", self.prefix)
        div.add(hidden)

        filter_id = "%s_%s" % (self.prefix, filter_name)
        div.set_id(filter_id)
        div.add_class("spt_filter_wdg")

        # add the enable/disable checkbox
        checkbox = CheckboxWdg('%s_enabled' % self.prefix)
   
        filter_data = FilterData.get()
        filter_data_map = filter_data.get_values_by_index(self.prefix, filter_index)
        #if filter_index == 0:
        #    checkbox.set_checked()
        if filter_index == -1:
            checkbox.set_checked()
        elif not filter_data_map:
            checkbox.set_checked()
        elif filter_data_map.get("prefix") == self.prefix:
            if filter_data_map.get( "%s_enabled" % self.prefix ) != "":
                checkbox.set_checked()

    
        checkbox.set_persist_on_submit()
        #checkbox.add_event("onclick", "spt.dg_table.disable_filter_cbk(this,'%s')" % filter_id)
        #checkbox.add_behavior({'type': 'click_up', 'cbjs_action':  "var top = document.id(this).getParent('.spt_search'); var el = top.getElement('.spt_search_num_filters'); el.innerHTML = ''; bvr.src_el.checked = false;"})
        checkbox.add_behavior({"type": "click_up", "cbjs_action" : "var top = bvr.src_el.getParent('.spt_search'); var el = top.getElement('.spt_search_num_filters'); el.innerHTML = '';",
        "propagate_evt": True})
        """
        checkbox.add_behavior( {
            'type': 'click_up',
            'cbjs_action': '''
            var top = bvr.src_el.getParent('.spt_search');
            var el = top.getElement('.spt_search_num_filters');
            el.innerHTML = 'cow';
            bvr.src_el.checked = false;
            '''
        })
        """
        span = DivWdg()
        span.add_style("float: left")
        span.add(checkbox)
        span.add('&nbsp;&nbsp;')
        div.add(span)


        # there are three parts to the filter:
        # 1) search type selector
        # 2) column selector
        # 3) the actual filter


        # 1. add a search type filter
        columns = None
        related_search_type = None
        if self.mode in ['parent', 'child', 'custom_related']:
            search_type_wdg = self.get_search_type_selector(filter_name, filter_index)
            #search_type = search_type_wdg.get_widget("selector").get_value()
            search_type = search_type_wdg.get_widget("selector").value
            if search_type and search_type != "*":
                #columns = self.get_columns_from_search_type(search_type)
                columns = SearchType.get_columns(search_type)
                columns = self.remove_columns(columns)
                related_search_type = search_type
            div.add( search_type_wdg )

            spacing = DivWdg('&nbsp; &nbsp;')
            spacing.add_style("float: left")
            div.add(spacing)

        elif self.mode in ['custom']:
            columns = self.element_names
        
        else:
            pass





        # 2. add the column selector
        filter_selector = self.get_column_selector(filter_name, filter_index, columns)
        div.add( filter_selector )
        selector = filter_selector.get_widget("selector")
        #columns = selector.get_values()
        columns = [selector.value]
        if columns:
            column = columns[0]
        else:
            column = None

        # get filter
        if self.mode == 'custom':
            filter_type_wdg = SpanWdg()
            filter_type_wdg.add_class("spt_filter_type_wdg")

            if column and column in self.element_names:
                filter = self.config.get_display_widget(column)

                # set the value s for this filter
                values = filter_data.get_values_by_index("custom", filter_index)
                filter.set_values(values)
            else:
                filter = ''


            filter_type_wdg.add(filter)


        else:
            search_type = self.search_type
            if related_search_type:
                search_type = related_search_type
            search_type_obj = SearchType.get(search_type)
            if column == '_expression':
                column_type = 'expression'
            else:
                #column_type = search_type_obj.get_tactic_type(column)
                column_type = SearchType.get_tactic_type(search_type, column)
            filter_type_wdg = self.get_filter_type_wdg(column_type, filter_index, column=column)


        #spacing = DivWdg('&nbsp;&nbsp;')
        #spacing.add_style("float: left")
        #div.add(spacing)

 
        div.add( filter_type_wdg )


        #buttons_list = [
        #        {'label': '+', 'tip': 'Add Filter', 'width': 25,
        #            'bvr': {'cbjs_action': 'spt.dg_table.add_filter(bvr.src_el)'} },
        #        {'label': '-', 'tip': 'Remove Filter', 'width': 24,
        #            'bvr': {'cbjs_action': 'spt.dg_table.remove_filter(bvr.src_el)'} },
        #]
        #buttons = TextBtnSetWdg( float="", buttons=buttons_list, spacing=6, size='small', side_padding=4 )


        from tactic.ui.widget import ActionButtonWdg
        add_button = ActionButtonWdg(title='+', tip='Add Filter', size='small')
        add_button.add_style("float: left")
        #add_button.add_style("margin-top: -2px")
        add_button.add_behavior( {
        'type': 'click_up',
        'cbjs_action': '''

        var element = bvr.src_el;
        var container = element.getParent(".spt_filter_container");
        var filter = element.getParent(".spt_filter_container_with_op");
        var op = filter.getElement(".spt_op");

        var op_value;
        if (op == null) {
            op_value = 'and';
        } else {
            op_value = op.getAttribute("spt_op");
        }

        // get template
        var filter_top = element.getParent(".spt_filter_top");
        var filter_template = filter_top.getElement(".spt_filter_template_with_op");
        
        var filter_options = filter_top.getElement(".spt_filter_options");
        var filters = filter_options.getElements(".spt_filter_type_wdg");
        // clear the value in the textbox if any
        for (var k=0; k< filters.length; k++){
            input = filters[k].getElement("input");
            // hidden used for expression
            if (input && input.getAttribute('type') !='hidden' ) input.value ='';
        }
         
       

        // clone the filter
        var new_filter = spt.behavior.clone(filter_template);
        new_filter.addClass("spt_filter_container_with_op");
        new_filter.inject(filter, "after");
        var display = new_filter.getElement(".spt_op_display");

        var top = element.getParent(".spt_search");
        var filter_mode = top.getElement(".spt_search_filter_mode").value;
        if (filter_mode == 'custom') {
            display.innerHTML = op_value;
        }

        // make this into a new search filter
        var children = new_filter.getElements(".spt_filter_template");
        for (var i=0; i<children.length; i++) {
            var child = children[i];    
            child.addClass("spt_search_filter");
        }
        var children = new_filter.getElements(".spt_op_template");
        for (var i=0; i<children.length; i++) {
            var child = children[i];
            child.addClass("spt_op");
            
            child.setAttribute("spt_op", op_value);
        }


        '''
        } )

        sub_button = ActionButtonWdg(title='-', tip='Remove Filter', size='small')
        #sub_button.add_style("float: left")
        #sub_button.add_style("margin-top: -2px")
        sub_button.add_behavior( {
        'type': 'click_up',
        'cbjs_action': '''

        var element = bvr.src_el;
        var container = element.getParent(".spt_filter_container");
        //var search_filter = element.getParent(".spt_search_filter")
        var search_filter = element.getParent(".spt_filter_container_with_op")

        var all_filters = container.getElements(".spt_filter_container_with_op");
        if (all_filters.length == 1) {
            return;
        }

        if (all_filters[0] == search_filter) {
            // have to destoy the spacing and op for the first filter
            var second_filter = all_filters[1];
            var op = second_filter.getElement(".spt_op");
            op.destroy();
            var spacing = second_filter.getElement(".spt_spacing");
            spacing.destroy();
        }

        container.removeChild( search_filter );


        '''
        } )

        top_div = DivWdg()
        if filter_index != -1:
            top_div.add_class("spt_search_filter")
        else:
            top_div.add_class("spt_filter_template")

        top_div.add(div)
        top_div.add(add_button)
        top_div.add(sub_button)

        """
        horiz_layout = HorizLayoutWdg( 
            widget_map_list=[
                {'wdg': div,'style': ""},
                {'wdg': add_button,'style': ""},
                {'wdg': sub_button} ],
           spacing=0, float=""
        )
        top_div.add( horiz_layout )
        """
        return top_div



    def get_search_type_selector(self, filter_name, filter_index):
        '''Get a select of the search_types for children or parent'''
        search_type_selector = DivWdg()
        search_type_selector.add_style("float: left")
        
        filter_id = "%s_search_type" % (self.prefix)
        search_type_select = SelectWdg(filter_id)
        search_type_select.add_style("width: 130px")
        search_type_select.add_empty_option('-- Related Type --')
        behavior = {
            'type': 'change',
            #'cbjs_action': 'spt.dg_table.set_filter2(evt, bvr)',
            'cbjs_action': '''

            var prefix = bvr.prefix;
            var selector = bvr.src_el;

            // get the column type mapping
            //var value = document.id(prefix+"_search_type_indexes").value;
            //value = value.replace(/'/g, '"')
            //var column_indexes = JSON.parse(value);
            var column_indexes = bvr.search_type_indexes;
            
            //var filter_types = document.id(prefix + '_filter_columns');
            var filter_types = spt.get_cousin(selector, '.spt_filter_top', '.' + prefix + '_filter_columns');

            // get a handle on all of the alternative filters
            var filters = filter_types.getChildren();
          
            // get the value of the column selector
            var value = selector.value;

            // WARNING: MAGIC!!

            // get the target and the column index
            var filter = selector.getParent('.spt_filter_wdg');
            var column_index = column_indexes[value];
            if (column_index == undefined) {
                column_index = 0;
            }
            // clone and replace
            var clone = filters[column_index].clone();
            var replacee = filter.getElement('.spt_filter_columns');
            filter.replaceChild( clone, replacee );
            spt.show(clone);
            //clone.style.display = "inline";

            ''',
            'prefix': self.prefix,
            'search_type_indexes': self.search_type_indexes
        }
        search_type_select.add_behavior(behavior)


        #schema = Schema.get()
        if self.mode in ['child', 'parent','related', 'custom_related']:
            self.labels = [x.split("/")[1].title() for x in self.related_types]
            search_type_select.set_option("values", self.related_types)
            search_type_select.set_option("labels", self.labels)
            self.set_filter_value(search_type_select, filter_index)

        search_type_selector.add(search_type_select, "selector")
        return search_type_selector


    def get_column_selector(self, filter_name, filter_index, columns=[]):
        '''Get a select of the columns for a search type'''
        filter_selector = DivWdg(css='spt_filter_columns')
        filter_selector.add_style("float: left")

        filter_id = "%s_column" % (self.prefix)
        column_select = SelectWdg(filter_id)
        column_select.add_empty_option()

        if not columns:
            columns = self.columns

        columns.sort()
        # avoid putting straight column names
        labels = [Common.get_display_title(x) for x in columns]

        # add an expression entry
        columns = columns[:]
        columns.append("_expression")
        labels = labels[:]
        labels.append("**Expression")

        column_select.add_style("max-width: 120px")
        column_select.set_option("values", columns)
        column_select.set_option("labels", labels)
        column_select.add_empty_option("-- Attribute --")
        column_select.set_persist_on_submit()
        #column_select.add_event("onchange", "spt.dg_table.set_filter(this, '%s')" % self.prefix)
        column_select.add_behavior({
            'type': 'change',
            'cbjs_action': '''

            selector = bvr.src_el;
            prefix = "%s"

            // get the column type mapping
            var filter_top = selector.getParent(".spt_filter_top");
            var hidden = filter_top.getElement(".spt_filter_indexes");
            var value = hidden.value;

            value = value.replace(/'/g, '"')
            var column_indexes = JSON.parse(value);

            // get a handle on all of the alternative filters
            var filter_options = filter_top.getElement(".spt_filter_options");
            var filters = filter_options.getElements(".spt_filter_type_wdg");

            // get the value of the column selector
            var value = selector.value;

            // get the target and the column index
            //var filter = document.id(selector.parentNode.parentNode);
            var filter = document.id(selector).getParent(".spt_filter_wdg")
            var column_index = column_indexes[value];
            if (typeof(column_index) == "undefined") {
                column_index = 0;
            }

            // clone and replace
            var clone = spt.behavior.clone( filters[column_index] )
            //var children = filter.getChildren();
            //filter.replaceChild( clone, children[4] );
            var filter_type_wdg = filter.getElement(".spt_filter_type_wdg");
            filter.replaceChild( clone, filter.getElement(".spt_filter_type_wdg") );

            clone.style.display = "inline";

            ''' % self.prefix
            })
        self.set_filter_value(column_select, filter_index)
        filter_selector.add(column_select, "selector"  )
        
        return filter_selector


    def set_filter_value(self, filter, filter_index, default=''):
        # templates do not have values
        if filter_index == -1:
            filter.set_value(default, set_form_value=False)
            return

        # set the value
        filter_id = filter.get_name()
        filter_data = FilterData.get()
        values = filter_data.get_values_by_index(self.prefix, filter_index)
        value = values.get(filter_id)
        if value:
            filter.set_value(value, set_form_value=False)



    def get_filter_type_wdg(self, type, filter_index, column=None):
        ''' getting the filter for comparision operators'''
        if type not in ['string', 'varchar', 'float', 'integer', 'timestamp','time','datetime2','login','expression', 'timecode','boolean']:
            print("WARNING: FilterWdg: type [%s] not supported, using 'string'" % type)
            type = 'string'
        
        filter_span = DivWdg()
        filter_span.add_style("float: left")
        filter_span.add_class("spt_filter_type_wdg")
        filter_span.add_color("color", "color")
        
        web = WebContainer.get_web()
        
        relation_select = None
        if type in ["string", "varchar", "boolean"]:
            if type == 'boolean':
                relations = ["is", "is not", "is empty", "is not empty"]
            else:
                relations = ["is", "is not", "contains", "does not contain", "is empty", "is not empty", "starts with", "ends with", "does not start with", "does not end with", "in", "not in", "is distinct"]
                
            relation_select = SelectWdg("%s_relation" % self.prefix)
            relation_select.add_style("width: 80px")
            relation_select.add_style("float: left")
            relation_select.remove_empty_option()
            relation_select.set_option("values", relations)
            relation_select.set_persist_on_submit()

            self.set_filter_value(relation_select, filter_index)
            filter_span.add(relation_select)
            
          
            #from tactic.ui.input import LookAheadTextInputWdg
            #value_text = LookAheadTextInputWdg(name="%s_value"%self.prefix,search_type=self.search_type, column="id")
            value_text = TextWdg("%s_value" % self.prefix)
            value_text.add_class("form-control")
            value_text.set_persist_on_submit()
            value_text.add_class('spt_filter_text')
            value_text.add_style("float", "left")
            value_text.add_style("height", "30")
            value_text.add_style("width", "250")
            value_text.add_style("margin", "0px 5px")
            self.set_filter_value(value_text, filter_index)
            filter_span.add(value_text);
            
            value_text.add_behavior( {
            'type': 'keyup',
            'cbjs_action': '''
                var key = evt.key;
                if (key == 'enter') {
                    evt.stop();
                    spt.dg_table.search_cbk( {}, {src_el: bvr.src_el} );
                }
            '''
            } )

            #behavior = {
            #    'type': 'keyboard',
            #    'kbd_handler_name': 'TextSearch'
            #}
            #value_text.add_behavior(behavior)

           
            
            
           
            
          
         
        elif type in ['integer', 'float', 'currency']:
            relations = ["is equal to", "is greater than", "is less than", "in", "not in", "is empty", "is not empty", "is distinct"]
            relation_select = SelectWdg("%s_relation" % self.prefix)
            relation_select.set_option("values", relations)
            relation_select.add_style("float", "left")
            relation_select.add_style("width", "80px")
            relation_select.set_persist_on_submit()
            self.set_filter_value(relation_select, filter_index)
            filter_span.add(relation_select)

            value_text = TextWdg("%s_value" % self.prefix)
            value_text.add_class("form-control")
            value_text.add_styles("float: left; width: 250; margin: 0px 5px")
            value_text.set_persist_on_submit()

            #behavior = {
            #    'type': 'keyboard',
            #    'kbd_handler_name': 'TextSearch'
            #}
            #value_text.add_behavior(behavior)

            value_text.add_behavior( {
                'type': 'keyup',
                'cbjs_action': '''
                    var key = evt.key;
                    if (key == 'enter') {
                        evt.stop();
                        spt.dg_table.search_cbk( {}, {src_el: bvr.src_el} );
                    }
                '''
            })
            self.set_filter_value(value_text, filter_index)
            filter_span.add(value_text)

        elif type in  ['time','timestamp','datetime2']:
            relations = ["is newer than", "is older than", "is on", "is empty", "is not empty"]
            labels = ["is after", "is before", "is on", "is empty", "is not empty"]
            relation_select = SelectWdg("%s_relation" % self.prefix)
            relation_select.set_option("values", relations)
            relation_select.set_option("labels", labels)
            relation_select.add_style("width: 100px")
            relation_select.add_style("float: left")
            relation_select.set_persist_on_submit()
            self.set_filter_value(relation_select, filter_index)
            filter_span.add(relation_select)

            options = ["1 day", '2 days', '1 week', '1 month', "-1 day", "-2 days", "-1 week", "-1 month"]
            labels = ["1 day ago", '2 days ago', '1 week ago', '1 month ago', '1 day from now', '2 days from now', '1 week from now', '1 month from now']
            another_select = SelectWdg("%s_select" % self.prefix)
            another_select.add_class('spt_time_filter')
            another_select.add_style("width: 100px")
            another_select.add_style("float: left")
            another_select.add_empty_option("-- Select --")
            another_select.set_option("values", options)
            another_select.set_option("labels", labels)
            another_select.add_style("width: 80px")
            another_select.set_persist_on_submit()
            self.set_filter_value(another_select, filter_index)
            filter_span.add(another_select)
            
            or_div = DivWdg(" or &nbsp; ", css='small spt_time_filter')
            or_div.add_style('width','20px')
            or_div.add_style('float','left')
            filter_span.add(or_div)
            from tactic.ui.widget import CalendarInputWdg
            value_cal = CalendarInputWdg("%s_value" % self.prefix)
            value_cal.add_class('spt_time_filter')
            value_cal.add_style("float", "left")

            value_cal.set_option('show_activator', True)
            #value_cal.set_option('show_text', True)
            value_cal.set_option('show_time', True)
            
            value_cal.get_top().add_styles('float: right;width: 230px') 
            value_cal.set_persist_on_submit()
            
            self.set_filter_value(value_cal, filter_index)
            filter_span.add(value_cal)

        elif type in ['login']:

            relations = ["is", "is not", "contains", "does not contain", "is empty", "is not empty","starts with", "ends with"]
            relation_select = SelectWdg("%s_relation" % self.prefix)
            relation_select.set_option("values", relations)
            relation_select.set_persist_on_submit()
            self.set_filter_value(relation_select, filter_index)
            filter_span.add(relation_select)

            value_text = CheckboxWdg("%s_user" % self.prefix)
            value_text.set_persist_on_submit()
            self.set_filter_value(value_text, filter_index)
            filter_span.add(value_text)
            filter_span.add("{user}")

            filter_span.add(" or ")

            value_text = TextWdg("%s_value" % self.prefix)
            value_text.add_class("form-control")
            value_text.set_persist_on_submit()
            self.set_filter_value(value_text, filter_index)
            filter_span.add(value_text)


        elif type in ['expression']:
            relation_hidden = HiddenWdg("%s_relation" % self.prefix)
            relation_hidden.set_value("expression")
            filter_span.add(relation_hidden)

            filter_span.add(" ")

            op_filter = SelectWdg("%s_op" % self.prefix)
            op_filter.set_option("labels", "have|do not have|match (slow)|do not match (slow)")
            op_filter.set_option("values", "in|not in|match|do not match")
            op_filter.add_style("float", "left")
            op_filter.add_style("width: 80px")
            self.set_filter_value(op_filter, filter_index)
            filter_span.add(op_filter)
            filter_span.add(" ")


            value_text = TextAreaWdg("%s_value" % self.prefix)
            value_text.add_style("vertical-align: top")
            value_text.add_style("height", "30px")
            value_text.add_style("width", "250px")
            value_text.add_style("margin-left", "5px")
            value_text.set_persist_on_submit()
            self.set_filter_value(value_text, filter_index, default='@SOBJECT()')
            filter_span.add(value_text)

        elif type in ['timecode']:
            filter_span.add(" ")

            relations = ["is timecode before", "is timecode after", "is timecode equal", "is empty"]
            labels = ["is before", "is after", "is equal", "is empty"]
            relation_select = SelectWdg("%s_relation" % self.prefix)
            relation_select.set_option("values", relations)
            relation_select.set_option("labels", labels)
            relation_select.set_persist_on_submit()
            self.set_filter_value(relation_select, filter_index)
            filter_span.add(relation_select)


            value_text = TextWdg("%s_value" % self.prefix)
            value_text.add_class("form-control")
            value_text.add_style("float", "left")
            value_text.set_persist_on_submit()
            self.set_filter_value(value_text, filter_index)
            filter_span.add(value_text)

        # expression is passed in in the HiddenWdg and we want to ignore 
        if relation_select:

            relation_select.set_option('show_missing', False)
            relation_select.add_behavior({
            'type': 'change',
            'cbjs_action': '''
                var select = bvr.src_el;
                var textbox = select.getNext('input');
                
                var hide_options = ["is empty", "is not empty", "is distinct"];

                if (textbox) {
                    if (hide_options.contains(select.value))            
                        textbox.style.display='none';
                    else
                        textbox.style.display='';
                } else {
                    // datetime 
                    var elems = select.getParent('.spt_filter_wdg').getElements('.spt_time_filter');
                    if (hide_options.contains(select.value))      
                        for (var i=0; i<elems.length; i++) {
                            elems[i].style.display= 'none';
                        }
                    else {
                         for (var i=0; i<elems.length; i++) {
                            elems[i].style.display= '';
                        }
                    }
                }
                    

            '''
            })   
        return filter_span



  

  
    def alter_search(self, search):

        filter_data = FilterData.get()
        values_list = filter_data.get_data()
        
       
        
        relevant_values_list = []
        for i, values in enumerate(values_list):
            # hacky
            if not values.has_key("%s_column" % self.prefix):
                continue

            # check if this filter is enabled
            enabled = values.get("%s_enabled" % self.prefix)
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on', 'true'])
            if not is_enabled:
                # don't skip here as Compound search needs to know all the enabled and 
                # non-enabled ones. Plus, alter_sobject_search will handle that
                pass
                #continue

            relevant_values_list.append(values)
        
        
        if self.filter_mode != 'custom':
            search.add_op("begin")

        if self.mode in ["child", "parent", 'custom_related']:
            self.alter_child_search(search, relevant_values_list)
        elif self.mode == "custom":
            self._alter_custom_search(search, relevant_values_list)
        elif self.mode == "sobject":
            self._alter_sobject_search(search, relevant_values_list, self.prefix)

        assert self.filter_mode
        if self.filter_mode != 'custom':
            # this closes the lstack
            search.add_op(self.filter_mode)



    def alter_child_search(self, search, values_list):
       
        if not values_list:
            return
        # NOTE: this assumes all search_types are the same

        # filter out non-enabled make sure not all enabled are empty
        value_dict = {}
        for values in values_list:
            search_type = values.get("%s_search_type" % self.prefix)
            if not search_type:
                search_type = search.get_base_search_type()

            if search_type == '*':
                continue
           
            # NOTE: this is done here instead of the relevant_values_list in alter_search to work with Compound Search better
            enabled = values.get("%s_enabled" % self.prefix)
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on', 'true'])
            if not is_enabled:
                continue
           

            # text box takes precedence, select is applicable for timestamps 
            value = values.get("%s_value" % self.prefix)
            if not value:
                value = values.get("%s_select" % self.prefix)
            # at last check for special relation like is (not) empty, is distinct
            if not value:
                value = values.get("%s_relation" % self.prefix)
                if value in ['is empty','is not empty','is distinct']:
                    value = True
                else:
                    value = False

            has_value_list = value_dict.get(search_type)
            if not has_value_list:
                has_value_list = [value]
                value_dict[search_type] = has_value_list
            else:
                has_value_list.append(value)

        
        # build a dict to show which search type actually got some values 
        # specified
        for key, values in value_dict.items():   
            for val in values:
                if val:
                    value_dict[key] = True
                    break
            else:
                value_dict[key] = False


        # analyze the operators and get all of the search ops that apply to
        # this mode
        search_ops = []
        if self.filter_mode == 'custom':
            filter_data = FilterData.get()
            all_search_ops = filter_data.get_values_by_index("search_ops", 0)
            if all_search_ops:
                all_modes = all_search_ops.get("modes")
                all_levels = all_search_ops.get("levels")
                all_ops = all_search_ops.get("ops")
                # backwards compatibility
                if not all_modes:
                    all_modes = []
                    for i in range(0,len(all_levels)):
                        all_modes.append("None")

                for op_mode, op_level, op_op in zip(all_modes, all_levels, all_ops):
                    if op_mode not in self.mode:
                        continue

                    search_ops.append( [op_level, op_op] )
        else:
            search_ops =  None


        child_search = None
        child_searches = []
        upper_ops = []
        last_search_type = None
        for i, values in enumerate(values_list):

            enabled = values.get("%s_enabled" % self.prefix)
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on', 'true'])

            if not is_enabled:
                continue

            search_type = values.get("%s_search_type" % self.prefix)
            if not search_type:
                if self.filter_mode == "custom":
                    search_type = search.get_base_search_type()
                else:
                    self._alter_sobject_search(search, [values], self.prefix)
                    child_search = None
                    last_search_type = None
                    continue


            if not value_dict.get(search_type):
                # set a new child search if there is any break
                child_search = None
                last_search_type = None
                continue


            if search_type != last_search_type:
                child_search = None
            
            if not search_ops:
                level = 0
                op = self.filter_mode
                if op == 'custom':
                    op = 'and'
            elif i > 0:
                search_op = search_ops[i-1]
                level, op = search_op
                if search_type != last_search_type:
                    child_search = None
                    upper_ops.append(op)
                if level == 1:
                    # if level is 1 then start a new search.  Level 1 operators
                    # form independent child searches
                    child_search = None
                    # also, search ops do not go to the alter_sobject_search
                    # and are handled here
                    search_op = None
                    upper_ops.append(op)
            else:
                # for the first search, we have a new search
                child_search = None
                level = 0
                op = 'and'

            is_new_search = False
            if not child_search:
                is_new_search = True
                # create a new one
                child_search = Search(search_type)
                child_searches.append(child_search)
                #TODO: This is a little presumptious that if there is a 
                # search type column use it as a filter.  It can greatly reduce
                # the number of returned results but may be a problem in a
                # small percentatge of cases if this filter is not desireable
                # for some reason
                ''' 
                if child_search.column_exists('search_type'):
                    sobject_type = search.get_search_type()
                    child_search.add_filter("search_type", sobject_type)
                '''
                # this is added even if Compound Search is not selected
                child_search.add_op('begin')

        
            # a child filter only send one value list at a time
            self._alter_sobject_search(child_search, [values], self.prefix, use_ops=False)
            
            # this is added even if Compound Search is not selected as they are independent
            if not is_new_search:
                child_search.add_op(op)

            last_search_type = search_type
            
        # go through all of the child searches and add the relationships
        all_sub_results_empty = True
        begin_idx = len(search.get_select().get_wheres())
        
        for i, child_search in enumerate(child_searches):
          
            self.add_child_search_filter(search, child_search)

            # apply upper level op on custom mode
            if self.filter_mode == 'custom' and i > 0:
                search.add_op( upper_ops[i-1] )
                search.add_op('begin', begin_idx)

        
    def add_child_search_filter(search, child_search):
        search.add_relationship_search_filter(child_search)


    def _alter_custom_search(self, search, values_list):

        for i, values in enumerate(values_list):

            enabled = values.get("%s_enabled" % self.prefix)
            column = values.get("%s_column" % self.prefix)

            # check if this filter is enabled
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on','true'])
            if not is_enabled:
                continue

            if column in self.element_names:
                widget = self.config.get_display_widget(column)
                widget.set_values(values)
                # FIXME: what to do about values_list
                widget.alter_search(search)


    def _alter_sobject_search(self, search, values_list, prefix, use_ops=True):
        num_enabled = self.alter_sobject_search(search, values_list, prefix, use_ops=use_ops)
        self.num_filters_enabled += num_enabled



    def _add_time_filter(cls, search, column, value, op):
        '''internal method for time related filtering'''

        from dateutil import parser
        try:
            if re.search('day|week|hour|month',value, flags=re.IGNORECASE):
                is_date = False
            else:
                parser.parse(value)
                is_date = True
        except:
            is_date = False

        #import re
        #p = re.compile("\d+-\d+-\d")
        #if re.match(p, value):
        if is_date:
            search.add_where("\"%s\" %s '%s'" % (column, op, value) )
        elif value == 'xxx':
            from dateutil.relativedelta import relativedelta
            from datetime import datetime
            import calendar

            today = datetime.today()
            vars = {
            'MONDAY': today + relativedelta(weekday=calendar.MONDAY),
            'TUESDAY': today + relativedelta(weekday=calendar.TUESDAY),
            'WEDNESDAY': today + relativedelta(weekday=calendar.WEDNESDAY),
            'THURSDAY': today + relativedelta(weekday=calendar.THURSDAY),
            'FRIDAY': today + relativedelta(weekday=calendar.FRIDAY),
            'SATURDAY': today + relativedelta(weekday=calendar.SATURDAY),
            'SUNDAY': today + relativedelta(weekday=calendar.SUNDAY)
            }
            value = Search.eval(value, vars=vars, single=True)
            search.add_filter(column, value, op=op)

        elif ' ' in value:
            num, type = value.split(" ", 1)
            num = int(num)
            now = search.get_database_impl().get_timestamp_now(num,type,op='-')
            search.add_filter(column, now, op=op, quoted=False)
        else:
            raise SearchInputException('Invalid value [%s] is entered. Click on the link again. '%value) 

    _add_time_filter = classmethod(_add_time_filter)


    def _evaluate_value(cls, value):
        value = Search.eval(value, single=True)
        return value
    _evaluate_value = classmethod(_evaluate_value)


    def alter_sobject_search(cls, search, values_list, prefix, use_ops=True, mode='sobject'):
        '''alter directly the sobject search
            @mode: sobject|child|parent'''

        num_enabled = 0


        search_type_obj = search.get_search_type_obj()
        base_search_type = search.get_base_search_type()
        search_type = search.get_full_search_type()

        # get the operations
      
        filter_data = FilterData.get()
        search_ops = filter_data.get_values_by_prefix("search_ops")

        # get the filter mode (if it is used)
        filter_mode = filter_data.get_values_by_prefix("filter_mode")
        if filter_mode:
            filter_mode = filter_mode[0].get("filter_mode")
        else:
            filter_mode = 'and'

        # find out which values list is enabled for compound search
        values_list_enabled = []
        valid_values_list = []
        if use_ops and filter_mode == 'custom':
            for i, values in enumerate(values_list):
                # filter out provided search_type if it exists in values_list
                item_search_type = values.get("%s_search_type" % prefix)

                if item_search_type and base_search_type != item_search_type:
                    continue

                enabled = values.get("%s_enabled" % prefix)
                column = values.get("%s_column" % prefix)
                relation = values.get("%s_relation" % prefix)

                # text box takes precedence 
                value = values.get("%s_value" % prefix)
                if not value:
                    value = values.get("%s_select" % prefix)

                # curly braces
                if value and value.startswith("{") and value.endswith("}"):
                    value = cls._evaluate_value(value) 

                column_type = SearchType.get_tactic_type(search_type, column)


                # check if this filter is enabled
                if enabled == None:
                    # by default, the filter is enabled
                    is_enabled = True
                else:
                    is_enabled = (str(enabled) in ['on','true'])

                if is_enabled and relation in ['is empty', 'is not empty', 'is distinct']:
                    is_enabled = True
                elif not value or not column or not relation:
                    is_enabled = False
                        
                values_list_enabled.append(is_enabled)
                if is_enabled: 
                    valid_values_list.append(values)

        if valid_values_list:
            values_list = valid_values_list
        
        level_0_count = 0
        if use_ops and search_ops and values_list_enabled:
            levels = []
            ops = []
            search_ops = search_ops[0]
            all_levels = search_ops.get("levels")
            all_ops = search_ops.get("ops")
            all_modes = search_ops.get("modes")
           

            # filter down to those ops applicable for Filter subsection
            look_ahead = False
         
            filtered_levels = []
            filtered_ops = []
            filtered_modes = []

            # filter for the applicable levels and ops according to mode
            for op_mode, op_level, op_op in zip(all_modes, all_levels, all_ops):
                if op_mode != mode:
                    continue
                filtered_levels.append(op_level)
                filtered_ops.append(op_op)
                filtered_modes.append(op_mode)


            for idx, (op_mode, op_level, op_op) in enumerate(zip(filtered_modes, filtered_levels, filtered_ops)):
                if idx + 1 > len(values_list_enabled):
                    continue
                # the level 0 after a disabled filter is ignored
                if op_level == 0 and idx + 1 < len(values_list_enabled): 
                    if values_list_enabled[idx] == True or values_list_enabled[idx+1] ==True:    
                        level_0_count += 1

                    if values_list_enabled[idx] == False and look_ahead==False:
                        continue
                    # look ahead to disable if applicable
                    if values_list_enabled[idx+1] ==False:
                        look_ahead = True
                        continue

                
                if idx + 1 >= len(values_list_enabled):
                    continue

                # reset level 0 count when it reaches level 1
                if op_level == 1:
                    if values_list_enabled[idx] == True:
                        level_0_count += 1
                    look_ahead = False
                    # if preceding level 0s are all False, skip
                    if level_0_count == 0:
                        continue
                    level_0_count =0 
                    if values_list_enabled[idx+1] == True:
                        level_0_count += 1

               
                levels.append(op_level)
                ops.append(op_op)
                    
            
        else:
            levels = None
            ops = None

        # discard the trailing dangling level 1 op 
        if levels and levels[-1] == 1 and level_0_count == 0:
            levels.pop()
            ops.pop()


      
        begin_idx = len(search.get_select().get_wheres())
        upper_begin_idx = begin_idx
        for i, values in enumerate(values_list):
            
            # filter out provided search_type if it exists in values_list
            item_search_type = values.get("%s_search_type" % prefix)
            if item_search_type and base_search_type != item_search_type:
                continue

            enabled = values.get("%s_enabled" % prefix)
            column = values.get("%s_column" % prefix)
            relation = values.get("%s_relation" % prefix)
            if enabled and column:
                num_enabled += 1

            # text box takes precedence 
            value = values.get("%s_value" % prefix)
            if not value:
                value = values.get("%s_select" % prefix)

            # curly braces
            if value and value.startswith("{") and value.endswith("}"):
                value = cls._evaluate_value(value) 

            #column_type = search_type_obj.get_tactic_type(column)
            column_type = SearchType.get_tactic_type(search_type, column)


            # check if this filter is enabled
            if enabled == None:
                # by default, the filter is enabled
                is_enabled = True
            else:
                is_enabled = (str(enabled) in ['on','true'])
            if not is_enabled:
                continue
    
            special_relation = False
            # handle all of the types
            if relation == "is empty":
                if column_type in ['boolean','integer','float','currency','time','timestamp','datetime2', 'uniqueidentifier']:
                    search.add_filter(column, None)
                else:
                    search.add_where("(\"%s\" = '' or \"%s\" is NULL)" % (column, column) )
                special_relation = True

            elif relation == "is not empty":
                if column_type in ['boolean','integer','float','currency','time','timestamp','datetime2']:
                    search.add_where("(\"%s\" is not NULL)" % column )
                else:
                    search.add_where("(\"%s\" != '' and \"%s\" is not NULL)" % (column, column) )
                special_relation = True

            elif relation == "is distinct":
                #search.set_distinct_col(column)
                #search.add_group_aggregate_filter(column, "id", 'min')
                if column.find('|') != -1:
                    column = column.split('|')
                search.add_distinct_filter(column)
                special_relation = True

            # this must be old
            user = values.get("%s_user" % prefix)
            if user:
                search.add_user_filter()
                continue
        


            if not value or not column or not relation or special_relation:
	        begin_idx = GeneralFilterWdg.add_ops(search, values_list,  levels, ops, i, begin_idx)
                continue

            if relation == "is":
                search.add_filter(column, value)


            elif relation == "is not":
                search.add_op('begin')
                search.add_filter(column, value, op='!=')
                search.add_filter(column, None)
                search.add_op('or')

            elif relation == "contains":
                search.add_regex_filter(column, value, op="EQI")
            elif relation == "does not contain":
                search.add_op('begin')
                search.add_regex_filter(column, value, op="NEQI")
                search.add_filter(column, None)
                search.add_op('or')
           
            elif relation == "starts with":
                search.add_where("(\"%s\" like '%s%%')" % (column, value) )
            elif relation == "ends with":
                search.add_where("(\"%s\" like '%%%s')" % (column, value) )

            elif relation == "does not start with":
                search.add_where("(\"%s\" not like '%s%%')" % (column, value) )
            elif relation == "does not end with":
                search.add_where("(\"%s\" not like '%%%s')" % (column, value) )



            # integer / float comparisons
            elif relation == "is equal to":
                search.add_where("(\"%s\" = %s)" % (column, value) )
            elif relation == "is greater than":
                search.add_where("(\"%s\" > %s)" % (column, value) )
            elif relation == "is less than":
                search.add_where("(\"%s\" < %s)" % (column, value) )

            elif relation == "in":
                values = value.split("|")
                search.add_filters(column, values)
            elif relation == "not in":
                values = value.split("|")
                search.add_filters(column, values, op='not in')


            # date comparisons
            elif relation in ["is older than", "is before"]:
                cls._add_time_filter(search, column, value, '<=')
            elif relation in ["is newer than", "is after"]:
                cls._add_time_filter(search, column, value, '>=')
            elif relation in ["is on"]:
                date = Date(db_date = value)
                value = date.get_db_date()
                cls._add_time_filter(search, column, value, '>=')
                date.add_days(1)
                value2 = date.get_db_date()
                cls._add_time_filter(search, column, value2, '<')
            # time code
            elif relation == "is timecode before":
                timecode = TimeCode(timecode=value)
                frames = timecode.get_frames()
                search.add_filter(column, frames, op='<=')
            elif relation == "is timecode after":
                timecode = TimeCode(timecode=value)
                frames = timecode.get_frames()
                search.add_filter(column, frames, op='>=')
            elif relation == "is timecode equal":
                timecode = TimeCode(timecode=value)
                frames = timecode.get_frames()
                search.add_filter(column, frames, op='=')



            elif relation == "expression":
                op = values.get("%s_op" % prefix)
                if not op:
                    op = 'in'

                if op in ['in','not in']:
                    results = Search.eval(value)
                    # check here rather than letting add_relationship_filters nullifying the whole search
                    if results:
                        search.add_relationship_filters(results, op=op)
                    elif op == 'in':
                        search.set_null_filter()
                else:
                    if op == 'do not match':
                        op = 'not in'
                    else:
                        op = 'in'

                    ids = []
                    sobjects = Search( search.get_search_type() ).get_sobjects()
                    for sobject in sobjects:
                        result = Search.eval(value, sobject, single=True)
                        if result == True:
                            ids.append( sobject.get_id() )
                    if not ids:
                        search.set_null_filter()
                    else:
                        search.add_filters("id", ids, op=op)
                        

            else:
                print("WARNING: relation [%s] not implemented" % relation)
                continue


            # handle the ops
            if filter_mode != 'custom':
                continue

            if ops == None:
                continue

         
            begin_idx = GeneralFilterWdg.add_ops(search, values_list, levels, ops, i, begin_idx)


        # handle the hardcoded 2nd level ops
        if filter_mode == 'custom' and ops != None:
            for count, op in enumerate(ops):
                level = levels[count]
                if level == 1:
                    search.add_op(op)
                    search.add_op('begin', upper_begin_idx)

        #print("FINAL", search.select.wheres)
        return num_enabled

    alter_sobject_search = classmethod(alter_sobject_search)
    
    def add_ops(search, values_list, levels, ops, i, begin_idx):
        '''add level 0 op if it is the end of the values list or if it encounters level 1 op'''
        if not levels:
	    return begin_idx
        op = None
        # this is the end of values_list
        if i+1 == len(values_list): 
            if levels[i-1] == 0:
                op = ops[-1]
        # this is level 1
        elif levels[i] == 1:
            # skip level 1
            op = ops[i-1]
        if op:
            search.add_op(op)
            search.add_op('begin', begin_idx)
            begin_idx = len(search.get_select().get_wheres())
         
        return begin_idx	
    add_ops = staticmethod(add_ops)

class HierarchicalFilterWdg(BaseFilterWdg):
    '''A filter that takes the hierarchical schema into account'''

    def get_args_keys(self):
        return {
        'prefix': 'the prefix name for all of the input elements',
        'search_type': 'the search_type that this filter will operate on'
        }


    def init(self):
        self.schema = Schema.get()
        if not self.schema:
            self.parent_type = None
            self.select = None
            return

        web = WebContainer.get_web()
        self.search_type = web.get_form_value("filter|search_type")
        if not self.search_type:
            self.search_type = self.options.get("search_type")
        if not self.search_type:
            self.search_type = self.kwargs.get("search_type")

        self.parent_type = self.schema.get_parent_type(self.search_type)
        self.parent_type = "prod/asset_library"
        if not self.parent_type:
            self.select = None
        else:
            if self.kwargs.get('refresh') == 'false':
                self.select = SelectWdg("filter|%s" % self.parent_type)
            else:
                self.select = FilterSelectWdg("filter|%s" % self.parent_type)


    def get_parent_type(self):
        return self.parent_type


    def get_display(self):

        widget = Widget()

        if not self.select:
            return widget

        if not self.schema:
            Environment.add_warning("No schema defined")
            widget.add("No schema defined")
            return widget


        if not self.search_type:
            Environment.add_warning("HierarchicalFilterWdg", "HierarchicalFilterWdg: Cannot find current search_type")
            widget.add("Cannot find current search_type")
            return widget

        span = SpanWdg(css="med")
        parent_type = self.get_parent_type()
        if parent_type:
            parent_type_obj = SearchType.get(parent_type)
            span.add("%s: " % parent_type_obj.get_value("title"))

        # assume that there is a code in the parent
        self.select.add_empty_option("-- Select --")
        self.select.set_option("query", "%s|code|code" % self.parent_type)
        span.add(self.select)

        widget.add(span)

        return widget


    def alter_search(self, search):
        if not self.select:
            return
        if not self.parent_type:
            return
        if not self.schema:
            return

        parent_code = self.select.get_value()
        parent = Search.get_by_code(self.parent_type, parent_code)
        if not parent:
            return
        parent.children_alter_search(search, self.search_type)





class SObjectSearchFilterWdg(BaseFilterWdg):
    '''Basic Combination Search usually at the top of the Search Box'''
    def get_args_keys(self):
        return {
        'prefix': 'the prefix name for all of the input elements',
        'search_type': 'the search_type that this filter will operate on',
        'columns': 'searchable columns override'
        }


    def init(self):
        self.search_type = self.options.get("search_type")
        if not self.search_type:
            self.search_type = self.kwargs.get("search_type")

        stype_columns = SearchType.get_columns(self.search_type)

        self.columns = self.kwargs.get('columns')
        if self.columns:
            self.columns = self.columns.split('|')
        else: 
            self.columns = self.options.get("columns")
            if self.columns:
                self.columns = self.columns.split('|')

        if not self.columns:

            self.columns = []

            # need a way to specify the columns
            sobject = SearchType.create(self.search_type)
            if hasattr(sobject, 'get_search_columns'):
                self.columns = sobject.get_search_columns()

            self.columns.append('id')
            if 'code' in stype_columns:
                self.columns.append('code')

        
        self.prefix = self.kwargs.get("prefix")
        #self.text.set_persist_on_submit(prefix=self.prefix)
        #self.set_filter_value(self.text, filter_index)
        self.stype_columns = []
        self.text_value = ''

    def get_value(self):

        filter_data = FilterData.get()
        values = filter_data.get_values_by_index(self.prefix, 0)
        return values.get("%s_search_text"%self.prefix)
        


    def alter_search(self, search):
        ''' customize the search here '''
        #search.add_where("begin")
        
        self.stype_columns = search.get_columns()
        
        values = FilterData.get().get_values_by_index(self.prefix, 0)
        # check if this filter is enabled
        enabled = values.get("%s_enabled" % self.prefix)
        value = self.get_value()

        if enabled == None:
            # by default, the filter is enabled
            is_enabled = True
        else:
            is_enabled = (str(enabled) in ['on', 'true'])

        if not is_enabled:
            return

        if is_enabled and value:
            self.num_filters_enabled += 1



        if not value:
            return
        self.text_value = value
        search.add_op("begin")

        for column in self.columns:
            if not column in self.stype_columns:
                continue

            # id and code should be exact matches
            if column == 'id':
                try:
                    search.add_filter(column, int(value))
                except ValueError:
                    pass
            elif column != 'keywords':
                search.add_filter(column, value)


        #filter_string = Search.get_compound_filter(value, self.columns)
        #if filter_string:
        #    search.add_where(filter_string)


        # add keywords
        column = 'keywords'
        if value and column in self.stype_columns:
            search.add_text_search_filter(column, value)

        search.add_op("or")

       

    def set_columns(self, columns):
        self.columns = columns

    def get_display(self):
        widget = Table()
        widget.add_row()
        widget.add_style("margin-left: 25px")

        widget.add_style("padding: 8px")
        # this is required
        widget.add_class("spt_search_filter")

        hidden = HiddenWdg("prefix", self.prefix)
        widget.add(hidden)

        if not self.columns:
            raise SetupException('A list of column names expected for SearchFilterWdg')
        
        checkbox = CheckboxWdg('%s_enabled' % self.prefix)

        # this trick only works with when there is only one checkbox with this prefix
        checkbox.set_persist_on_submit(prefix=self.prefix)
        td = widget.add_cell(checkbox)
        td.add_style("padding-right: 10px")
        
        
        if 'keywords' in self.stype_columns:
            self.columns.append('keywords')
        
        # this name corresponds to alter_search()
        name = '%s_search_text' % self.prefix
        self.text = TextInputWdg(name=name, hint_text=', '.join(self.columns))
        self.text.set_attr("size","50")
        self.text.add_behavior( {
            'type': 'keyup',
            'cbjs_action': '''
                var key = evt.key;
                if (key == 'enter') {
                    evt.stop();
                    spt.dg_table.search_cbk( {}, {src_el: bvr.src_el} );
                }
            '''
            } )
        
        
        widget.add_cell(self.text)
        
        if self.text_value:
            self.text.set_value(self.text_value)

        self.text.add_style("display", "inline")
        
        hint_msg = '[ %s ] columns are used in this search.' %', '.join(self.columns)
        hint = HintWdg(hint_msg)
        widget.add_cell(hint)

        return widget

class SubmissionFilterWdg(BaseFilterWdg):


    def init(self):
        self.prefix = self.kwargs.get("prefix")
        self.type = self.kwargs.get('type')
        self.item_filter = None

    def get_display(self):
        widget = DivWdg()
        widget.add_class("spt_search_filter")
        widget.add_style("padding: 5px")

        # Always enable this filter
        #checkbox = CheckboxWdg('%s_enabled' % self.prefix)
        #checkbox.set_persist_on_submit(prefix=self.prefix)
        #widget.add(SpanWdg(checkbox, css='small'))

        from pyasm.prod.web import BinFilterSelectWdg
        hidden = HiddenWdg("prefix", self.prefix)
        widget.add(hidden)
        bin_filter = BinFilterSelectWdg(name='%s_bin_select'%self.type, type=self.type)
        bin_filter.add_empty_option('-- Select a bin --', value=SelectWdg.NONE_MODE)
        #bin_filter.add_behavior({'type': 'change', 
        #    "cbjs_action" : bin_filter.get_save_script()})


        values = FilterData.get().get_values_by_index(self.prefix, 0)
        bin_id = values.get("%s_bin_select" % self.prefix)
        if bin_id:
            bin_filter.set_value(bin_id)
        
        #bin_filter.set_persistence()
        widget.add(bin_filter)

        
        #widget.add(self.item_filter)
        return widget

    def alter_search(self, search):
        values = FilterData.get().get_values_by_index(self.prefix, 0)
        #if values.get('%s_enabled'%self.prefix) != 'on':
        #    return
        # check if this filter is enabled
        bin_id = values.get("%s_bin_select" % self.prefix)
        if not bin_id or bin_id == SelectWdg.NONE_MODE:
           #search.add_filter('id','-1')
           search.add_where("id in (select submission_id from "\
            " submission_in_bin"\
            " where bin_id in (select id from bin where type = '%s') )"%self.type )
        elif bin_id:
           search.add_where("id in (select submission_id from "\
            " submission_in_bin"\
            " where bin_id = %s)" %bin_id)


        search.add_order_by('timestamp desc')

        # should work on a proper parent search
        """ 
        all_sobjs = search.get_sobjects()
        # tell the search it is not done
        #search.is_search_done = False

        # this filter is created based on the existing search parameters
        from pyasm.prod.web import SubmissionItemFilterWdg
        self.item_filter = SubmissionItemFilterWdg(all_sobjs)
        
        item_value = values.get('item_filter')
        self.item_filter.alter_search(search, item_value) 
        """


class SnapshotFilterWdg(BaseFilterWdg):

    
    def init(self):
        # will be passed in as a state in alter_search() for initial value 
        self.publish_search_type = ''
        self.prefix = self.kwargs.get("prefix")
        from pyasm.prod.web import DateSelectWdg, UserFilterWdg
        self.date_sel = DateSelectWdg('publish_date', is_filter=False)
        self.user_filter = UserFilterWdg(pref='single')
        self.enabled = False

    def get_display(self):
        widget = DivWdg()
        widget.add_class("spt_search_filter")
        widget.add_style("padding: 5px")

        hidden = HiddenWdg("prefix", self.prefix)
        widget.add(hidden)

        checkbox = CheckboxWdg('%s_enabled' % self.prefix)
        if self.enabled:
            checkbox.set_checked()
        widget.add(SpanWdg(checkbox, css='small'))

        # add search_type select
        from tactic.ui.widget import SearchTypeSelectWdg
        self.search_type_sel = SearchTypeSelectWdg('publish_search_type', mode=SearchTypeSelectWdg.CURRENT_PROJECT)

        # set the value based on what just gets published (default to prod/asset)

        if self.publish_search_type:
            self.search_type_sel.set_value(self.publish_search_type)

        self.search_type_sel.set_option('default','prod/asset')
        
        span = SpanWdg("Type: ", css='small smaller')
        span.add(self.search_type_sel)
        widget.add(span)

        # add date select

        label_list = ['Today','Last 2 days', 'Last 5 days', 'Last 30 days']
        value_list = ['today','1 Day', '4 Day','29 Day']
        
        self.date_sel.set_label(label_list)
        self.date_sel.set_value(value_list)
        self.date_sel.set_persistence() 
        self.date_sel.add_behavior({'type' : 'change',
            'cbjs_action': "%s;" \
            % (self.date_sel.get_save_script())})
        span = SpanWdg(css='smaller')
        span.add(self.date_sel)
        
        span.add(self.user_filter)
        widget.add(span)

        return widget

    def alter_search(self, search):
        

        values = FilterData.get().get_values_by_index(self.prefix, 0)
               
        snapshot_filter_enabled = self.state.get('snapshot_filter_enabled')
        if not snapshot_filter_enabled:
            snapshot_filter_enabled = values.get('%s_enabled'%self.prefix) 
       
        # check if this filter is enabled
        if snapshot_filter_enabled != 'on':
            return
        self.enabled = True

         # if set explicitly, then use the publish search type
        # since it is the one being displayed as well
        self.publish_search_type = self.state.get('publish_search_type')
        if self.publish_search_type:
            value = self.publish_search_type
        else:
            value = values.get("publish_search_type")
            self.publish_search_type = value

        
        from pyasm.biz import Project
        project_name = Project.get_project_name()
        if value:
            # the full name may have been stored in WidgetSettings
            if '?' in value:
                search_str = value
            else:
                search_str = '%s?project=%s' %(value,project_name)
            search.add_filter('search_type', search_str)
        else:
            # filter by prod/asset as default
            search_str = 'prod/asset?project=%s' %(project_name)
            search.add_filter('search_type', search_str)

        user = values.get('user_filter')
        if user:
            search.add_filter('login', user)
        
        value = values.get("publish_date")
        if not value or value == SelectWdg.NONE_MODE:
            return
        search.add_where(self.date_sel.get_where(value)) 



class WorkHourFilterWdg(BaseFilterWdg):

    def init(self):
        # will be passed in as a state in alter_search() for initial value 
        self.prefix = self.kwargs.get("prefix")
        from pyasm.widget import WeekTableElement
        self.week_filter_name = WeekTableElement.CAL_NAME
        self.work_date_selector = CalendarInputWdg(WeekTableElement.CAL_NAME, show_week=True)
        self.work_filter = None

        self.enabled = False
   
    def get_display(self):
        from pyasm.common import Date
        div = DivWdg(css="spt_search_filter")
        div.add_style("padding: 5px")

        hidden = HiddenWdg("prefix", self.prefix)
        div.add(hidden)

        checkbox = CheckboxWdg('%s_enabled' % self.prefix)
        if self.enabled:
            checkbox.set_checked()
        div.add(SpanWdg(checkbox, css='small'))
        login_filter = None

        """
        if self._has_user_wdg_access():
            login_filter = UserFilterWdg()
            login_filter.navigator.set_submit_onchange()
        """
        #project_filter = ProjectFilterWdg()
        div.add(login_filter)

        #work_date_selector.set_persist_on_submit()
        selected_date = self.work_date_selector.get_value()
        #work_date_selector.set_onchange_script('document.form.submit()')
        date = None
        if selected_date:
            date = Date(db_date = selected_date)
        else: # take today if not set
            date = Date() 
        selected_date = date.get_db_date()
       
        from pyasm.prod.web import WeekFilterWdg
        self.week_filter = WeekFilterWdg(selected_date, self.week_filter_name)

        date_span = SpanWdg("Date: ", css='med')
        date_span.add(self.work_date_selector)
        div.add(date_span)
        div.add(self.week_filter)
        return div


    def alter_search(self, search):
        # always filter just for current user for now
        search.add_filter('login', Environment.get_user_name())

        # check if this filter is enabled
        values = FilterData.get().get_values_by_index(self.prefix, 0)
        
        if values.get('%s_enabled'%self.prefix) != 'on':
            return
        selected_year = ''
        date = None
        selected_date = values.get(self.week_filter_name)
        if selected_date:
            date = Date(db_date = selected_date)
        else: # take today if not set
            date = Date() 
        selected_date = date.get_db_date()
        if selected_date:
            selected_year = selected_date.split('-', 2)[0]
        if selected_year:
            search.add_filter('year', selected_year)

        if selected_date:
            week_value = date.get_week()
            search.add_filter('week', week_value)

        #if login_filter:
        #    login_filter.alter_search(search)
        #else:
        search.add_project_filter()


class NotificationLogFilterWdg(BaseFilterWdg):
    '''used in My Notifications'''
    def init(self):
        self.prefix = self.kwargs.get("prefix")

    def get_display(self):
        # nothing to draw really, it's for internal search
        div = DivWdg(css="spt_search_filter")
        div.add_style("padding: 5px")

        hidden = HiddenWdg("prefix", self.prefix)
        div.add(hidden)

        return div


    def alter_search(self, search):
        
        # Do some built in search
        project_code = Project.get_project_code()
        user_name = Environment.get_user_name()

        # get all the notifications that were sent to you
        sub_search = Search("sthpw/notification_login")
        sub_search.add_filter("login", user_name)
        sub_search.add_filter("project_code", project_code)
        #search.add_filter("type", "to")

        notification_logins = sub_search.get_sobjects()
        notification_ids = SObject.get_values(notification_logins, "notification_log_id", unique=True)

        project_code = Project.get_project_code()
        search.add_filter("project_code", project_code)
        search.add_filters("id", notification_ids)

class ShotFilterWdg(BaseFilterWdg):
    '''used in Shot Loader page'''
    def init(self):
        self.prefix = self.kwargs.get("prefix")
        self.search_type = self.kwargs.get("search_type")
        self.seq_search_type = self.kwargs.get("sequence_search_type")
        from tactic.ui.input import ShotNavigatorWdg
        self.shot_navigator = ShotNavigatorWdg(shot_search_type=self.search_type, sequence_search_type=self.seq_search_type)
    
    def get_display(self):
        div = DivWdg(css='spt_search_filter')
        hidden = HiddenWdg("prefix", self.prefix)
        div.add(hidden)
        div.add(self.shot_navigator)
        return div

    def alter_search(self, search):
        values = FilterData.get().get_values_by_index(self.prefix, 0)
        seq_code = ''
        if values:
            shot_code = values.get('shot_code')
            seq_code = values.get('seq_select')
        else:    
            shot_code = self.shot_navigator.get_value()

        #search = Search(self.search_type)
        if shot_code:
            if search.get_base_search_type() == self.search_type:
                search.add_filter('code', shot_code)
            else:
                shot_search = Search(self.search_type)
                shot_search.add_filter('code', code)
                search.add_relationship_search_filter(shot_search)
        elif seq_code:
            seq_search = Search(self.seq_search_type)
            seq_search.add_filter('code', seq_code)
            search.add_relationship_search_filter(seq_search)

