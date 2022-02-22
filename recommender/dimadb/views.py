from rest_framework import permissions, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import date, datetime
from django.forms.models import model_to_dict
from django.db.models import Q, Count, F
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from django.apps import apps
from .serializers import *
from .models import *
from .content_based_recommender import ContentBasedRecommender
from .utils import *
from pathlib import Path

import random
import json
import uuid
import os
import pydash
import urllib3
import environ

# Read configure file
base_dir = Path(__file__).resolve().parent.parent
module_dir = os.path.dirname(__file__)
mapping_template_file_path = os.path.join(module_dir, 'configuration/mapping_template.json')
schema_table_file_path = os.path.join(module_dir, 'configuration/schema_table.json')
schema_detail_file_path = os.path.join(module_dir, 'configuration/schema_detail.json')

# Initialise environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(base_dir, '.env'))

# Global varial
API_KEY = env('API_KEY')
IP_DOMAIN = env('IP_DOMAIN')

@api_view(['GET'])
def home(request):
    try:
        # Initialize KPI reports
        web_activity_report = []
        event_report = []
        product_report = []
        traffics = {}

        # Total number of web activities (interactions)
        web_activities = len(Interaction.objects.all())
        # Total number of sessions (a session includes multiple interactions)
        sessions = len(Interaction.objects.values('session_id').distinct())
        # Total number of web activities by page location
        pages = list(Interaction.objects.all().values('page_location').annotate(total=Count('page_location')).order_by('-total'))
        # Total number of web activities by device categories
        device_categories = Interaction.objects.all().values('device_category').annotate(total=Count('device_category'))
        for category in list(device_categories):
            type = category['device_category']
            traffics[type] = category['total']

        # Web activities report - Total number of web activities by event name
        web_activity_data = Interaction.objects.all().values('event_name').annotate(total=Count('event_name'))
        web_activity_report = [(item['event_name'], item['total']) for item in list(web_activity_data)]
        # Cultural event report  - Total number of cultural events by event type
        event_data = Events.objects.all().values('event_type').annotate(total=Count('event_type'))
        event_report = [(item['event_type'], item['total']) for item in list(event_data)]
        # Cutural product report - Total number of cultural products by product type
        product_data = Products.objects.all().values('product_type').annotate(total=Count('product_type'))
        product_report = [(item['product_type'], item['total']) for item in list(product_data)]

        # Add info for report to generate charts
        reports = [
            {
                'id': 'activity-chart',
                'title': 'Percentage of web activities by event name',
                'data': web_activity_report,
                'type': 'pie',
            },
            {
                'id': 'event-chart',
                'title': 'Percentage of evenement by type',
                'data': event_report,
                'type': 'column'
            },
            {
                'id': 'product-chart',
                'title': 'Percentage of article by type',
                'data': product_report,
                'type': 'column'
            },
        ]

        return Response({'reports': reports,
                         'sessions': sessions,
                         'webActivities': web_activities,
                         'traffic': traffics,
                         'pages': pages}, status=status.HTTP_200_OK)

    except Exception as exception:
        return Response({'message': exception})


class ItemList(APIView):  
    # Get list of items (all rows) from a table
    def get(self, request, item_type):
        try:
            import_id = request.GET.get('importId', None)
            # Read config file
            item_list_schema = get_json_info(schema_table_file_path, item_type)
            # Get info (model_name of item, list required fields to show, ...)
            model_name = item_list_schema['model_name']
            fields = item_list_schema['fields']
            view_detail = item_list_schema['view_detail']
            Model = apps.get_model(app_label='dimadb', model_name=model_name)
            
            if (import_id is not None):
                items = Model.objects.filter(import_id=import_id).values(*fields)
            else:
                items = Model.objects.all().values(*fields)
            return Response({
                'items': items,
                'isViewDetail': view_detail,
            }, status=status.HTTP_200_OK)

        except Exception as exception:
            return Response({'message': exception})


class ItemDetail(APIView):
    # Get item detail (detail of a row) from a table
    def get(self, request, item_type, pk, format=None):
        try:
            # Read config file
            item_detail_schema = get_json_info(schema_detail_file_path, item_type)
            item_detail = get_item_detail_form(pk, item_detail_schema)
            return Response(item_detail)
        except Exception as exception:
            return Response({'message': exception})
    
    # Update info
    def put(self, request, item_type, pk, format=None):
        try:
            item_form = json.loads(request.body)
            update_item_info(item_form)
            return Response({'message': 'Update successfully'}, status=status.HTTP_200_OK)
        except Exception as exception:
            return Response({'message': exception})
    
    # Delete info
    def delete(self, request, item_type, pk, format=None):
        try:
            item_form = json.loads(request.body)
            delete_item_info(item_form)
            return Response({'message': 'Delete successfully'}, status=status.HTTP_200_OK)
        except Exception as exception:
            return Response({'message': exception})
    
    # New info
    def post(self, request, item_type, pk, format=None):
        try:
            item_form = json.loads(request.body)
            update_item_info(item_form)
            return Response({'message': 'Create successfully'}, status=status.HTTP_200_OK)
        except Exception as exception:
            return Response({'message': exception})


# Get data(row) from a table(model)
def get_model_object(model_name, pk):
    if (pk != 'form'):
        try:
            Model = apps.get_model(app_label='dimadb', model_name=model_name)
            event = Model.objects.get(id=pk)
            return model_to_dict(event)
        except Model.DoesNotExist:
            return {}
    else:
        return {}


# Get all information of an object from several tables (event information coming from event, geolocation, ...)
def get_item_detail_form(pk, schema_detail):
    form_attributes = {}
    # Get info from schema_detail
    model_name = schema_detail['model_name']
    fields = schema_detail['fields']
    m2m_tables = []
    o2m_tables = []
    if ('m2m_tables' in schema_detail.keys()):
        m2m_tables = schema_detail['m2m_tables']
    if ('o2m_tables' in schema_detail.keys()):
        o2m_tables = schema_detail['o2m_tables']

    # Query item from db
    Model = apps.get_model(app_label='dimadb', model_name=model_name)
    obj = get_model_object(model_name, pk)

    if ('id' in obj.keys()):
        obj_id = obj['id']
    else:
        obj_id = None
        
    # List attributes consists field names in primary table
    for field in fields:
        form_attributes[field] = {}
        attribute_type = Model._meta.get_field(field).get_internal_type()
        attribute_choices = Model._meta.get_field(field).choices
        # Assign value for each field of item
        if (field in obj.keys()):
            form_attributes[field]['value'] = obj[field]
        else:
            form_attributes[field]['value'] = ''
        # Assign data type for each field of item
        if (attribute_choices != None):
            form_attributes[field]['type'] = 'select'
            form_attributes[field]['choices'] = [
                value for (value, name) in attribute_choices]
        else:
            if (attribute_type == 'IntegerField'):
                form_attributes[field]['type'] = 'integer'
            elif (attribute_type == 'DecimalField'):
                form_attributes[field]['type'] = 'decimal'
            elif (attribute_type == 'TextField'):
                form_attributes[field]['type'] = 'textarea'
            elif (attribute_type == 'DateTimeField' or attribute_type == 'DateField'):
                form_attributes[field]['type'] = 'date'
                if form_attributes[field]['value'] == '' or form_attributes[field]['value'] is None:
                    form_attributes[field]['value'] = ''
                else:
                    form_attributes[field]['value'] = form_attributes[field]['value'].strftime(
                        "%Y-%m-%d")
            else:
                form_attributes[field]['type'] = 'text'

    # List m2m tables consists additional info of item (geolocation, resource, etc.)
    # Ex: event - eventlocation(connected_table, who hold 2 primary keys of two tables) - geolocation(m2m)
    for m2m_table in m2m_tables:
        # Get config info
        m2m_display_name = m2m_table['display_name']
        connected_table = m2m_table['connected_table']
        connected_field1 = m2m_table['connected_field1']
        connected_field2 = m2m_table['connected_field2']
        # Get list of rows in m2m table
        form_attributes[m2m_display_name] = {}
        form_attributes[m2m_display_name]['type'] = 'm2m'
        form_attributes[m2m_display_name]['value'] = get_m2m_items(m2m_table, obj_id)
        # Create an empty form info for m2m table
        element_attributes = get_item_detail_form('form', m2m_table)
        element_attributes['connectedAttributes'] = get_item_detail_form('form', connected_table)
        element_attributes['connectedAttributes']['connected_field1'] = connected_field1
        element_attributes['connectedAttributes']['connected_field2'] = connected_field2
        form_attributes[m2m_display_name]['elementAttributes'] = element_attributes

    # List o2m tables conists additional info of item (geolocation, resource, etc.)
    # Ex: evet - eventpreference(o2m)
    for o2m_table in o2m_tables:
        o2m_display_name = o2m_table['display_name']
        connected_field = o2m_table['connected_field']
        # Get list of rows in o2m table
        form_attributes[o2m_display_name] = {}
        form_attributes[o2m_display_name]['type'] = 'o2m'
        form_attributes[o2m_display_name]['value'] = get_o2m_items(o2m_table, obj_id)
        element_attributes = get_item_detail_form('form', o2m_table)
        element_attributes['connected_field'] = connected_field
        form_attributes[o2m_display_name]['elementAttributes'] = element_attributes

    form_info = {
        'type': 'object',
        'id': uuid.uuid4(),
        'attributes': form_attributes,
        'removed': False,
        'status': 'new' if pk == 'form' else 'created',
        'name': model_name
    }

    return form_info


# Update item based on form sent from GUI
def update_item_info(form_info, connected_field1_id=None):
    status = form_info['status']
    obj_id = form_info['attributes']['id']['value']
    obj_info = filter_form_object_info(form_info['attributes'])
    model_name = form_info['name']
    Model = apps.get_model(app_label='dimadb', model_name=model_name)

    if ('connected_field' in form_info.keys()):
        connected_field = form_info['connected_field']
        obj_info[connected_field] = connected_field1_id

    if (status == 'new'):  # If new info created
        new_obj = Model(**obj_info)
        new_obj.save()
        update_multiple_items('m2m', form_info['attributes'], new_obj.id)
        update_multiple_items('o2m', form_info['attributes'], new_obj.id)
        if ('connectedAttributes' in form_info.keys()):
            connected_field2_id = new_obj.id
            create_connected_object(form_info['connectedAttributes'], connected_field1_id, connected_field2_id)
    elif (status == 'created'):     # If info updated
        Model.objects.filter(id=obj_id).update(**obj_info)
        updated_obj = Model.objects.get(id=obj_id)
        update_multiple_items('m2m', form_info['attributes'], updated_obj.id)
        update_multiple_items('o2m', form_info['attributes'], updated_obj.id)
        if ('connectedAttributes' in form_info.keys()):
            update_item_info(form_info['connectedAttributes'])
    else:                           # If info deleted
        delete_item_info(form_info)


# Delete row from database
def delete_item_info(form_info):
    obj_id = form_info['attributes']['id']['value']
    if (id != ''):
        model_name = form_info['name']
        Model = apps.get_model(app_label='dimadb', model_name=model_name)
        Model.objects.filter(id=obj_id).delete()
        delete_multiple_items('m2m', form_info['attributes'])
        delete_multiple_items('o2m', form_info['attributes'])
        if ('connectedAttributes' in form_info.keys()):
            delete_item_info(form_info['connectedAttributes'])


# Get all items in m2m table
def get_m2m_items(m2m_table, connected_field1_id):
    m2m_forms = []
    if connected_field1_id:
        # Get config info
        connected_table = m2m_table['connected_table']
        connected_field1 = m2m_table['connected_field1']
        connected_field2 = m2m_table['connected_field2']
        connected_model_name = connected_table['model_name']

        # Get connected model objects to query connected_field2_id
        ConnectedModel = apps.get_model(app_label='dimadb', model_name=connected_model_name)
        filter_params = {connected_field1: connected_field1_id}
        connected_objects = list(ConnectedModel.objects.filter(**filter_params))
        connected_objects = [model_to_dict(connected_obj) for connected_obj in connected_objects]

        # For each connected object (row) in connected table, query and create form for that connected object + foreign object
        for connected_obj in connected_objects:
            connected_form = get_item_detail_form(connected_obj['id'], connected_table)
            m2m_form = get_item_detail_form(connected_obj[connected_field2], m2m_table)
            m2m_form['connectedAttributes'] = connected_form
            m2m_form['connectedAttributes']['connected_field1'] = connected_field1
            m2m_form['connectedAttributes']['connected_field2'] = connected_field2
            m2m_forms.append(m2m_form)

    return m2m_forms


# Get all items in o2m table
def get_o2m_items(o2m_table, connected_field_id):
    o2m_forms = []
    if connected_field_id:
        # Get config info
        o2m_model_name = o2m_table['model_name']
        connected_field = o2m_table['connected_field']

        # Get o2m model objects
        O2MModel = apps.get_model(app_label='dimadb', model_name=o2m_model_name)
        filter_params = {connected_field: connected_field_id}
        o2m_objects = list(O2MModel.objects.filter(**filter_params))
        o2m_objects = [model_to_dict(obj) for obj in o2m_objects]

        # Create o2m item form (row)
        for o2m_obj in o2m_objects:
            o2m_form = get_item_detail_form(o2m_obj['id'], o2m_table)
            o2m_form['connected_field'] = connected_field
            o2m_forms.append(o2m_form)

    return o2m_forms


# Update/New alternately items in m2m/o2m table
def update_multiple_items(table_type, obj, connected_field1_id=None):
    for attribute in obj.keys():
        if attribute != 'id':
            if obj[attribute]['type'] == table_type:
                list_values = obj[attribute]['value']
                for value in list_values:
                    update_item_info(value, connected_field1_id)


# Delete alternately items in m2m table
def delete_multiple_items(table_type, obj):
    for attribute in obj.keys():
        if attribute != 'id':
            if obj[attribute]['type'] == table_type:
                list_values = obj[attribute]['value']
                for value in list_values:
                    delete_item_info(value)


# Create object in connected table (eventlocation, eventresource, etc)
def create_connected_object(form_info, connected_field1_id, connected_field2_id):
    connected_field1 = form_info['connected_field1']
    connected_field2 = form_info['connected_field2']
    model_name = form_info['name']

    obj_info = filter_form_object_info(form_info['attributes'])
    obj_info[connected_field1] = connected_field1_id
    obj_info[connected_field2] = connected_field2_id

    Model = apps.get_model(app_label='dimadb', model_name=model_name)
    obj = Model(**obj_info)
    obj.save()


#Mapping data in file with data model
def mapping_data(data, template):
    total = 0   # Total object rows in imported data
    count = 0   # Total object rows saved in database
    try:
        if isinstance(data, list):
            total = len(data)
            # Store history of import
            import_info = ImportInfo(table_name=template['model_name'])
            import_info.save()
            
            # Get info from schema_detail
            model_name = template['model_name']
            fields = template['fields']
            m2m_tables = []
            o2m_tables = []
            if ('m2m_tables' in template.keys()):
                m2m_tables = template['m2m_tables']
            if ('o2m_tables' in template.keys()):
                o2m_tables = template['o2m_tables']

            #Mapping
            for obj in data:
                obj_info = filter_imported_object_info(fields, obj)
                if obj_info:
                    # Store obj in primary table
                    obj_info['import_id'] = import_info.id
                    Model = apps.get_model(app_label='dimadb', model_name=model_name)
                    new_obj = Model(**obj_info)
                    new_obj.save()

                    # Store additional objs in m2m tables
                    for m2m_table in m2m_tables:
                        m2m_model_name = m2m_table['model_name']
                        m2m_sources = m2m_table['sources']

                        for source in m2m_sources:
                            m2m_objs = []
                            if 'array' not in source:
                                m2m_objs.append(obj)
                            else:
                                if (pydash.get(obj, source['array'])):
                                    m2m_objs = pydash.get(obj, source['array'])

                            for m2m_obj in m2m_objs:
                                m2m_obj_info = filter_imported_object_info(source['fields'], m2m_obj)
                                if (m2m_obj_info):
                                    m2m_obj_info['import_id'] = import_info.id
                                    M2MModel = apps.get_model(app_label='dimadb', model_name=m2m_model_name)
                                    new_m2m_obj = M2MModel(**m2m_obj_info)
                                    new_m2m_obj.save()

                                    # Store obj in connected table
                                    # Read configure info
                                    connected_table = source['connected_table']
                                    connected_field1 = source['connected_field1']
                                    connected_field2 = source['connected_field2']
                                    connected_model_name = connected_table['model_name']

                                    connected_obj_info = filter_imported_object_info(connected_table['fields'], m2m_obj)
                                    connected_obj_info[connected_field1] = new_obj.id
                                    connected_obj_info[connected_field2] = new_m2m_obj.id
                                    connected_obj_info['import_id'] = import_info.id
                                    ConnectedModel = apps.get_model(app_label='dimadb', model_name=connected_model_name)
                                    new_connected_obj = ConnectedModel(**connected_obj_info)
                                    new_connected_obj.save()

                    # Store additional objs in o2m tables
                    for o2m_table in o2m_tables:
                        o2m_model_name = o2m_table['model_name']
                        sources = o2m_table['sources']

                        for source in sources:
                            o2m_objs = []
                            if 'array' not in source:
                                o2m_objs.append(obj)
                            else:
                                if (pydash.get(obj, source['array'])):
                                    o2m_objs = pydash.get(obj, source['array'])

                            for o2m_obj in o2m_objs:
                                o2m_obj_info = filter_imported_object_info(source['fields'], o2m_obj)
                                if (o2m_obj_info):
                                    connected_field = source['connected_field']
                                    o2m_obj_info[connected_field] = new_obj.id
                                    o2m_obj_info['import_id'] = import_info.id
                                    O2MModel = apps.get_model(app_label='dimadb', model_name=o2m_model_name)
                                    new_o2m_obj = O2MModel(**o2m_obj_info)
                                    new_o2m_obj.save()

                count += 1
            return {'message': 'Import successfully' + '.\n' + 'Import ' + str(count) + '/' + str(total) + 'object(s).'}
        else:
            return {'message': 'Wrong json format'}
    except Exception as error:
        return {'message':  'There is an error(duplication, ...).\n' + 'Import ' + str(count) + '/' + str(total) + 'object(s).'}


# Some imported json file required to be reformated before mapping
def reformated_data(json_data, item_type, template_type):
    try:
        reformated_json_data = []
        # Each item type & each template type => reformat differently
        if (item_type == 'web-activity' and template_type == 'default'):
            list_required_attributes = ['event_date', 'items', 'event_name', 'device', 'geo']
            list_required_event_params = ['ga_session_id', 'page_title', 'page_location']
            for obj in json_data:
                new_obj = {}
                for attribute in list_required_attributes:
                    if attribute == 'event_date':
                        date = pydash.get(obj, attribute)
                        format_date = date[:4] + '-' + date[4:6] + '-' + date[6:8]
                        new_obj[attribute] = format_date
                    else:
                        new_obj[attribute] = pydash.get(obj, attribute)

                for param in obj['event_params']:
                    key = param['key']
                    values = param['value']
                    if (key in list_required_event_params):
                        for value in values:
                            if values[value] != None:
                                new_obj[key] = values[value]
                            else:
                                continue
                reformated_json_data.append(new_obj)
        return reformated_json_data
    except Exception as exception:
        return exception


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def import_json_file(request, item_type):
    try:
        # Get request info
        files = request.FILES.getlist('files[]')
        file = files[0]
        json_data = json.load(file)

        # Get template configuration info
        template_type = request.POST.get('template')
        if (template_type is None or template_type == ''):
            template_type = 'default'
        template = get_json_info(mapping_template_file_path, item_type + '.' + template_type)
        is_reformat = template['is_reformat']

        # Check reformat
        if is_reformat:
            json_data = reformated_data(json_data, item_type, template_type)

        #Mapping and saving in database
        mapping_result = mapping_data(json_data, template)
        return Response(mapping_result, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['GET'])
def get_mapping_templates(request, item_type):
    try:
        list_templates = []
        json_file = open(mapping_template_file_path)
        json_data = json.load(json_file)
        json_file.close()
        list_templates = [key for key in json_data[item_type]]
        return Response({'listTemplates': list_templates}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])

def import_api(request, item_type):
    try:
        # Get request info
        request_body = json.loads(request.body)
        url = request_body['url']
        bearer_token = request_body['bearerToken']
        template_type = request_body['template']

        # Get data from url
        http = urllib3.PoolManager()
        header = {'Accept': '*/*'}
        if (bearer_token != ''):
            header['Authorization'] = 'Bearer ' + bearer_token
        if (template_type is None or template_type == ''):
            template_type = 'default'
        response = http.request('GET', url, headers=header)
        response_body = json.loads(response.data)
        response_data = response_body['data']

        # Import
        mapping_template = get_json_info(mapping_template_file_path, item_type + '.' + template_type)
        mapping_result = mapping_data(response_data, mapping_template)

        return Response(mapping_result, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['GET'])
def get_import_info(request, item_type):
    try:
        tables = {
            "event": "events",
            "article": "products",
            "web-activity": "interaction"
        }
        snippets = ImportInfo.objects.filter(table_name=tables[item_type])
        serializer = ImportInfoSerializer(snippets, many=True)
        return Response({'items': serializer.data}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['DELETE'])
def delete_imported_items(request, item_type, pk):
    try:
        tables = {
            "event": ["events", "geolocation", "eventlocation", "resource", "eventresource", "businessentity", "entityeventrole"],
            "article": ["products", "resource", "productresource", "businessentity", "entityproductrole"],
            "web-activity": ["interaction", "geolocation", "interactionlocation", "eventpreference", "productpreference"]
        }

        for table in tables[item_type]:
            Model = apps.get_model(app_label='dimadb', model_name=table)
            Model.objects.filter(import_id=pk).delete()
        ImportInfo.objects.filter(id=pk).delete()
        
        return Response({}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


# Generate recommend api to retrieve recommendation
def generate_recommend_api(level, item_type, recommend_type, quantity, domain, item_id):
    api = IP_DOMAIN + '/dimadb/get-list-recommend/?'
    api += 'itemType=' + item_type
    api += '&level=' + level
    api += '&quantity=' + quantity

    if (recommend_type):
        api += '&recommendType=' + recommend_type
    if (domain):
        api += '&domain=' + domain
    if (item_id):
        api += '&itemId=' + item_id

    return api


# Get upcoming recommendation
def get_upcoming(table_name, sort_field, display_fields, quantity=1, domain=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    list_recommend_items = []
    filter_params = {}

    if (sort_field != ''):
        today = datetime.today()
        sort_field_name = sort_field + '__gte'
        filter_params[sort_field_name] = today

    if (domain is not None):
        if (table_name == 'events'):
            filter_params['event_type'] = domain
        elif (table_name == 'products'):
            filter_params['product_type'] = domain

    list_objs = Model.objects.filter(Q(**filter_params)).order_by(sort_field)
    list_objs = list(list_objs)

    for i in range(0, int(quantity)):
        if (i < len(list_objs)):
            obj = model_to_dict(list_objs[i])
            recommend_item = {}
            for field in list(display_fields):
                recommend_item[field] = obj[field]
            if (table_name == 'events'):
                recommend_item['location_name'] = get_location_name(obj['id'])
            list_recommend_items.append(recommend_item)
            
    if (len(list_recommend_items) == 0):
        list_recommend_items = get_random(table_name, sort_field, display_fields, quantity)

    return list_recommend_items


# Get most popular recommendation
def get_most_popular(table_name, sort_field, display_fields, quantity=1, domain=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    list_recommend_items = []
    filter_params = {}

    if (sort_field != ''):
        today = datetime.today()
        sort_field_name = sort_field + '__gte'
        filter_params[sort_field_name] = today

    if (domain is not None):
        if (table_name == 'events'):
            filter_params['event_type'] = domain
        elif (table_name == 'products'):
            filter_params['product_type'] = domain

    list_objs = Model.objects.filter(Q(**filter_params))
    list_objs = [model_to_dict(obj) for obj in list(list_objs)]
    list_new_objs = []

    for obj in list_objs:
        obj['score'] = 0  # Most popular score
        list_item_activities = []

        # Find web activities that contain this item
        if (table_name == 'events'):
            list_item_activities = EventPreference.objects.filter(event_id=obj['event_id'])
        elif (table_name == 'products'):
            list_item_activities = ProductPreference.objects.filter(product_id=obj['product_id'])

        # For each web activity, find important weight of web activity type
        for item_activity in list(list_item_activities):
            item_activity = model_to_dict(item_activity)
            try:
                activity = Interaction.objects.get(id=item_activity['activity_id'])
                activity_type = model_to_dict(activity)
                activity_type = activity_type['event_name']
                try:
                    activity_weight = WebActivityType.objects.get(name=activity_type)
                    obj['score'] = obj['score'] + model_to_dict(activity_weight)['value']
                except:
                    pass
            except:
                pass
        list_new_objs.append(obj)

    list_new_objs = sorted(list_new_objs, key=lambda d: d['score'], reverse=True)
    for i in range(0, int(quantity)):
        if (i < len(list_new_objs)):
            obj = list_new_objs[i]
            recommend_item = {}
            for field in list(display_fields):
                recommend_item[field] = obj[field]
            if (table_name == 'events'):
                recommend_item['location_name'] = get_location_name(obj['id'])
            list_recommend_items.append(recommend_item)
            
    if (len(list_recommend_items) == 0):
        list_recommend_items = get_random(table_name, sort_field, display_fields, quantity)

    return list_recommend_items


# Get similarity recommendation
def get_similar(table_name, sort_field, display_fields, quantity=1, item_id=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    list_similar_items = ContentBasedRecommender.recommend_items_by_items(table_name=table_name, items_id=item_id)
    list_recommend_items = []

    for i in range(0, int(quantity)):
        if (i < len(list_similar_items)):
            similar_obj = list_similar_items[i]
            obj = Model.objects.get(id=similar_obj['id'])
            obj = model_to_dict(obj)
            obj['similarity'] = similar_obj['similarity']
            recommend_item = {}
            for field in list(display_fields):
                recommend_item[field] = obj[field]
            if (table_name == 'events'):
                recommend_item['location_name'] = get_location_name(obj['id'])
            list_recommend_items.append(recommend_item)
            
    if (len(list_recommend_items) == 0):
        list_recommend_items = get_random(table_name, sort_field, display_fields, quantity)

    return list_recommend_items


# Get random recommendation
def get_random(table_name, sort_field, display_fields, quantity):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    list_recommend_items = []
    filter_params = {}

    if (sort_field != ''):
        today = datetime.today()
        sort_field_name = sort_field + '__gte'
        filter_params[sort_field_name] = today

    if (sort_field != ''):
        list_objs = Model.objects.filter(Q(**filter_params)).order_by(sort_field)
    else:
        list_objs = Model.objects.all()
        
    list_objs = list(list_objs)

    for i in range(0, int(quantity)):
        if (i < len(list_objs)):
            obj = model_to_dict(list_objs[i])
            recommend_item = {}
            for field in list(display_fields):
                if (field in obj):
                    recommend_item[field] = obj[field]
                else:
                    recommend_item[field] = 0
            if (table_name == 'events'):
                recommend_item['location_name'] = get_location_name(obj['id'])
            list_recommend_items.append(recommend_item)

    return list_recommend_items

# Get location name of event
def get_location_name(event_id):
    EventLocationModel = apps.get_model(app_label='dimadb', model_name='eventlocation')
    LocationModel = apps.get_model(app_label='dimadb', model_name='geolocation')
    location_name = ''
    
    event_location = EventLocationModel.objects.get(event_id=event_id)
    
    if (event_location):
        location = LocationModel.objects.get(id=event_location.location_id)
        location_name = location.location_name
        
    return location_name
    
    
# Get list of recommend items
def get_recommend_items(level, item_type, recommend_type, quantity, domain, item_id):
    list_recommend_items = []
    display_fields = {
        'Upcoming': {
            'events': ['id', 'event_id', 'event_name', 'event_type', 'next_date', 'end_date', 'description', "img", "url"]
        },
        'Most popular': {
            'events': ['id', 'event_id', 'event_name', 'event_type', 'next_date', 'end_date', 'score', 'description', "img", "url"],
            'products': ['id', 'product_id', 'product_name', 'product_type', 'score', 'description', "img", "url"]
        },
        'Similar': {
            'events': ['id', 'event_id', 'event_name', 'event_type', 'end_date', 'next_date', 'similarity', 'description', "img", "url"],
            'products': ['id', 'product_id', 'product_name', 'product_type', 'similarity', 'description', "img", "url"],
        }
    }

    if (level == 'Homepage'):
        if (recommend_type == 'Upcoming'):
            if (item_type == 'events'):
                list_recommend_items = get_upcoming(table_name=item_type, sort_field='end_date', display_fields=display_fields[recommend_type][item_type], quantity=quantity)
        if (recommend_type == 'Most popular'):
            if (item_type == 'events'):
                list_recommend_items = get_most_popular(table_name=item_type, sort_field='end_date', display_fields=display_fields[recommend_type][item_type], quantity=quantity)
            elif (item_type == 'products'):
                list_recommend_items = get_most_popular(table_name=item_type, sort_field='', display_fields=display_fields[recommend_type][item_type], quantity=quantity)
    elif (level == 'Domain'):
        if (recommend_type == 'Upcoming'):
            if (item_type == 'events'):
                list_recommend_items = get_upcoming(table_name=item_type, sort_field='end_date',display_fields=display_fields[recommend_type][item_type], quantity=quantity, domain=domain)
        if (recommend_type == 'Most popular'):
            if (item_type == 'events'):
                list_recommend_items = get_most_popular(table_name=item_type, sort_field='end_date', display_fields=display_fields[recommend_type][item_type], quantity=quantity, domain=domain)
            elif (item_type == 'products'):
                list_recommend_items = get_most_popular(table_name=item_type, sort_field='', display_fields=display_fields[recommend_type][item_type], quantity=quantity, domain=domain)
    else:
        if (item_type == 'events'):
            list_recommend_items = get_similar(table_name=item_type, sort_field='end_date', display_fields=display_fields['Similar'][item_type], quantity=quantity, item_id=item_id)
        elif (item_type == 'products'):
            list_recommend_items = get_similar(table_name=item_type, sort_field='', display_fields=display_fields['Similar'][item_type], quantity=quantity, item_id=item_id)

    return list_recommend_items


@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_list_recommend(request):
    try:
        # Authorization
        bearer_token = request.headers.get('Authorization')
        if (bearer_token == 'Bearer ' + API_KEY):
            # Read request info
            level = request.GET.get('level', None)
            item_type = request.GET.get('itemType', None)
            recommend_type = request.GET.get('recommendType', None)
            quantity = request.GET.get('quantity', None)
            domain = request.GET.get('domain', None)
            item_id = request.GET.get('itemId', None)
            list_recommend_items = get_recommend_items(level, item_type, recommend_type, quantity, domain, item_id)
            return Response({'itemType': item_type, 'recommendType': recommend_type, 'items': list_recommend_items}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Authorization failed'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as error:
        return Response({'message': error})

def get_embedded_link(api):
    css_link = '<link rel="stylesheet" href="' + IP_DOMAIN + '/static/dimadb/css/recommender.css">'
    div_link = '<div id="' + 'recommendItem' + '"></div>'
    js_link = '<script src="' + IP_DOMAIN + '/static/dimadb/js/recommender.js' + '"></script>'
    recommend_link = '<script>' + '\n'
    recommend_link += '\tconst recommendItems = getRecommend("' + api + '", "' + API_KEY + '");' + '\n'
    recommend_link += '\trecommendItems.then(res => {' + '\n'
    recommend_link += '\t\t//Handle recommend items here' + '\n'
    recommend_link += '\t\t//Uncomment below code if we need to show view results' + '\n'
    recommend_link += '\t\t//console.log(recommendItems);' + '\n'
    recommend_link += '\t\t//Uncomment below code if we need to show recommendation UI' + '\n'
    recommend_link += '\t\t//getListView("recommendItem", recommendItems);' + '\n'
    recommend_link += '\t});' + '\n'
    recommend_link += '</script>'
    
    embedded_link = css_link + '\n' + div_link + '\n' + js_link + '\n' + recommend_link
    return embedded_link

@api_view(['POST'])
def get_recommend_api(request):
    try:
        # Read request info
        body = json.loads(request.body)
        level = body['level']
        item_type = body['itemType']
        recommend_type = body['recommendType']
        quantity = body['quantity']
        domain = body['domain']
        item_id = body['itemId']
        #Get recommend api + recommend list
        api = generate_recommend_api(level, item_type, recommend_type, quantity, domain, item_id)
        list_recommend_items = get_recommend_items(level, item_type, recommend_type, quantity, domain, item_id)
        embedded_link = get_embedded_link(api)
        return Response({'items': list_recommend_items, 'api': api, 'apiKey': API_KEY, 'embeddedLink': embedded_link}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['POST'])
def train_similar_recommend(request):
    try:
        # Read request info
        body = json.loads(request.body)
        item_type = body['itemType']
        # Training
        ContentBasedRecommender.train_items_by_items(table_name=item_type)
        # Get similarity recommendation training info
        similar_train_info = get_similar_train_info()
        return Response({'similarTrainInfo': similar_train_info}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['GET'])
def get_recommend_info(request):
    try:
        # Get list domain(item_type)
        event_snippets = Events.objects.all()
        event_serializer = EventSerializer(event_snippets, many=True)
        event_types = Events.objects.values('event_type').distinct()
        event_types = [item['event_type'] for item in list(event_types)]

        article_snippets = Products.objects.all()
        article_serializer = ArticleSerializer(article_snippets, many=True)
        article_types = Products.objects.values('product_type').distinct()
        article_types = [item['product_type'] for item in list(article_types)]

        return Response({'events': event_serializer.data,
                         'products': article_serializer.data,
                         'eventTypes': event_types,
                         'articleTypes': article_types}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


# Get history of similarity recommendation training
def get_similar_train_info():
    try:
        list_item_types = [{'name': 'Événement', 'value': 'events'},
                           {'name': 'Article', 'value': 'products'}]
        for item_type in list_item_types:
            Model = apps.get_model(app_label='dimadb', model_name=item_type['value'])
            item_type['number_items'] = len(Model.objects.all())

            # Get total number of trained items
            if (LdaSimilarityVersion.objects.filter(item_type=item_type['value']).exists()):
                obj = LdaSimilarityVersion.objects.filter(item_type=item_type['value']).latest('created_at')
                item_type['latest_training_at'] = str(obj)
                item_type['number_trained_items'] = model_to_dict(obj)['n_products']
            else:
                item_type['latest_training_at'] = ''
                item_type['number_trained_items'] = 0

            # Get total number of items
            Model = apps.get_model(app_label='dimadb', model_name=item_type['value'])
            item_type['number_items'] = len(Model.objects.all())

        return list_item_types
    except Exception as error:
        return Response({'message': error})


@api_view(['GET'])
def get_configure_info(request):
    try:
        similar_train_info = get_similar_train_info()
        web_activity_types = Interaction.objects.values('event_name').distinct()
        web_activity_types = [item['event_name'] for item in list(web_activity_types)]
        existed_web_activity_types = WebActivityType.objects.values('name').distinct()
        existed_web_activity_types = [item['name'] for item in list(existed_web_activity_types)]
        web_activity_types = web_activity_types + existed_web_activity_types
        web_activity_types = list(dict.fromkeys(web_activity_types))

        web_activities_info = {}
        for activity_type in web_activity_types:
            try:
                activity_type_obj = WebActivityType.objects.get(name=activity_type)
                activity_type_obj = model_to_dict(activity_type_obj)
                web_activities_info[activity_type] = activity_type_obj['value']
            except:
                web_activities_info[activity_type] = 0

        return Response({'similarTrainInfo': similar_train_info, 'webActivityInfo': web_activities_info}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['POST'])
def update_activity_weight(request):
    try:
        # Read requestinfo
        body = json.loads(request.body)
        web_activity_types = body['webActivityInfo']

        #Update/new web activity type
        for type in web_activity_types:
            try:
                web_activities = list(WebActivityType.objects.filter(name=type))
                # Check whether type exists in WebActivityType table
                if (len(web_activities)):
                    web_activity = web_activities[0]
                    web_activity.value = web_activity_types[type]
                    web_activity.save()
                else:
                    new_activity_type = WebActivityType(name=type, value=web_activity_types[type])
                    new_activity_type.save()
            except:
                new_activity_type = WebActivityType(name=type, value=web_activity_types[type])
                new_activity_type.save()

        return Response({}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


# Generate report object (info, name, title, data)
def create_report(name, title, data, chart_type, is_change):
    return {
        'name': name,
        'title': title,
        'data': data,
        'type': chart_type,
        'isChange': is_change,
        'random': name + str(random.randint(0, 1000)),
    }


@api_view(['GET'])
def get_reports(request):
    try:
        start_date = request.GET.get('startDate', date.today())
        end_date = request.GET.get('endDate', date.today())
        group_type = request.GET.get('groupBy', 'daily')

        reports = []
        # Session:
        if (group_type == 'none'):
            web_activities = [{'type': 'all', 'sum': Interaction.objects.filter(
                visit_date__range=[start_date, end_date]).values('session_id').distinct().count()}]
        elif (group_type == 'daily'):
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date')).annotate(sum=Count('session_id', distinct=True))
        elif (group_type == 'weekly'):
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week').annotate(sum=Count('session_id', distinct=True))
        elif (group_type == 'monthly'):
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month').annotate(sum=Count('session_id', distinct=True))
        else:
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year').annotate(sum=Count('session_id', distinct=True))
        reports.append(create_report('session_report', 'The total number of web_activities',
                       web_activities, 'column', group_type == 'none'))

        # Web_activities:
        if (group_type == 'none'):
            web_activities = [{'type': 'all', 'sum': Interaction.objects.filter(
                visit_date__range=[start_date, end_date]).all().count()}]
        elif (group_type == 'daily'):
            web_activities = Interaction.objects.filter(visit_date__range=[
                                                        start_date, end_date]).values(day=F('visit_date')).annotate(sum=Count('id'))
        elif (group_type == 'weekly'):
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week').annotate(sum=Count('id'))
        elif (group_type == 'monthly'):
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month').annotate(sum=Count('id'))
        else:
            web_activities = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year').annotate(sum=Count('id'))
        reports.append(create_report('web_activities_report',
                       'The total number of web activities', web_activities, 'column', group_type == 'none'))

        # Web Activities device_category:
        if (group_type == 'none'):
            web_activities_device = Interaction.objects.filter(visit_date__range=[
                                                               start_date, end_date]).values(type=F('device_category')).annotate(sum=Count('id'))
        elif (group_type == 'daily'):
            web_activities_device = Interaction.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('device_category')).annotate(sum=Count('id'))
        elif (group_type == 'weekly'):
            web_activities_device = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('device_category')).annotate(sum=Count('id'))
        elif (group_type == 'monthly'):
            web_activities_device = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('device_category')).annotate(sum=Count('id'))
        else:
            web_activities_device = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('device_category')).annotate(sum=Count('id'))
        reports.append(create_report('session_device_report', 'The total number of web activities by device category',
                       web_activities_device, 'column', group_type == 'none'))

        # Web Activities browser:
        if (group_type == 'none'):
            web_activities_browser = Interaction.objects.filter(visit_date__range=[
                                                                start_date, end_date]).values(type=F('browser')).annotate(sum=Count('id'))
        elif (group_type == 'daily'):
            web_activities_browser = Interaction.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('browser')).annotate(sum=Count('id'))
        elif (group_type == 'weekly'):
            web_activities_browser = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('browser')).annotate(sum=Count('id'))
        elif (group_type == 'monthly'):
            web_activities_browser = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('browser')).annotate(sum=Count('id'))
        else:
            web_activities_browser = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('browser')).annotate(sum=Count('id'))
        reports.append(create_report('session_browser_report', 'The total number of web activities by browser',
                       web_activities_browser, 'column', group_type == 'none'))

        # Web Activities os:
        if (group_type == 'none'):
            web_activities_os = Interaction.objects.filter(visit_date__range=[
                                                           start_date, end_date]).values(type=F('operating_system')).annotate(sum=Count('id'))
        elif (group_type == 'daily'):
            web_activities_os = Interaction.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('operating_system')).annotate(sum=Count('id'))
        elif (group_type == 'weekly'):
            web_activities_os = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('operating_system')).annotate(sum=Count('id'))
        elif (group_type == 'monthly'):
            web_activities_os = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('operating_system')).annotate(sum=Count('id'))
        else:
            web_activities_os = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('operating_system')).annotate(sum=Count('id'))
        reports.append(create_report('session_os_report', 'The total number of web activities by operating system',
                       web_activities_os, 'column', group_type == 'none'))

        # Web Activities type:
        if (group_type == 'none'):
            web_activities_type = Interaction.objects.filter(visit_date__range=[
                                                             start_date, end_date]).values(type=F('event_name')).annotate(sum=Count('id'))
        elif (group_type == 'daily'):
            web_activities_type = Interaction.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('event_name')).annotate(sum=Count('id'))
        elif (group_type == 'weekly'):
            web_activities_type = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('event_name')).annotate(sum=Count('id'))
        elif (group_type == 'monthly'):
            web_activities_type = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('event_name')).annotate(sum=Count('id'))
        else:
            web_activities_type = Interaction.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('event_name')).annotate(sum=Count('id'))
        reports.append(create_report('session_activity_report', 'The total number of web activities by type',
                       web_activities_type, 'column', group_type == 'none'))

        return Response({'reports': reports}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})
