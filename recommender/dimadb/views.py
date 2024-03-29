from rest_framework import permissions, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import date, datetime, timedelta
from django.forms.models import model_to_dict
from django.db.models import Q, Count, F, Sum
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from django.apps import apps
from django.core.files.storage import default_storage
from .serializers import *
from .models import *
from .content_based_recommender import ContentBasedRecommender
from .utils import *
from pathlib import Path
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunReportRequest
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from slugify import slugify

import pandas as pd
import random
import json
import uuid
import os
import pydash
import urllib3
import dotenv

# Read configure file
base_dir = Path(__file__).resolve().parent.parent
module_dir = os.path.dirname(__file__)
mapping_template_file_path = os.path.join(module_dir, 'configuration/mapping_template.json')
schema_table_file_path = os.path.join(module_dir, 'configuration/schema_table.json')
schema_detail_file_path = os.path.join(module_dir, 'configuration/schema_detail.json')
ga4_json = os.path.join(module_dir, 'configuration/ga4.json')
ua_json = os.path.join(module_dir, 'configuration/ua.json')

# Initialize environment variables
dotenv.load_dotenv(os.path.join(base_dir, '.env'))

# Global vaos.environrial
API_KEY = os.environ['API_KEY']
IP_DOMAIN = os.environ['IP_DOMAIN']
scope = 'https://www.googleapis.com/auth/analytics.readonly'
dimensions = ['date', 'eventName', 'pageLocation', 'browser', 'deviceCategory', 'operatingSystem', 'country']
metrics = ['eventCount', 'sessions']
ua_dimensions = ['ga:date', 'ga:eventCategory', 'ga:pagePath', 'ga:browser', 'ga:deviceCategory', 'ga:operatingSystem', 'ga:country']
ua_metrics = ['ga:totalEvents', 'ga:sessions']

@api_view(['GET'])
def home(request):
    try:
        # Initialize KPI reports
        web_activity_report = []
        event_report = []
        product_report = []
        traffics = {}

        # Total number of web activities (interactions)
        web_activities_file = len(Interaction_f.objects.all())
        web_activities_ga = Interaction_ga.objects.all().aggregate(Sum('event_count'))['event_count__sum']
        if (web_activities_ga is None):
            web_activities_ga = 0
        web_activities = web_activities_file + web_activities_ga
        # Total number of sessions (a session includes multiple interactions)
        sessions_file = len(Interaction_f.objects.values('session_id').distinct())
        sessions_ga = Interaction_ga.objects.all().aggregate(Sum('session_count'))['session_count__sum']
        if (sessions_ga is None):
            sessions_ga = 0
        sessions = sessions_file + sessions_ga
        # Total number of web activities by page location
        pages_file = Interaction_f.objects.all().values('page_location').annotate(total=Count('page_location'))
        pages_ga = Interaction_ga.objects.all().values('page_location').annotate(total=Sum('event_count'))
        pages = list(pages_file) + list(pages_ga)
        if (len(pages)):
            pages = pd.DataFrame(pages).groupby(['page_location'], as_index=False).sum().to_dict('r')
            pages = sorted(pages, key=lambda k : k['total'], reverse=True)
        
        # Total number of web activities by device categories
        device_categories_file = Interaction_f.objects.all().values('device_category').annotate(total=Count('device_category'))
        device_categories_ga = Interaction_ga.objects.all().values('device_category').annotate(total=Sum('event_count'))
        device_categories = list(device_categories_ga) + list(device_categories_file)
        for category in list(device_categories):
            type = category['device_category']
            if (type not in traffics):
                traffics[type] = 0
            traffics[type] += category['total']

        # Web activities report - Total number of web activities by event name
        web_activity_data_file = Interaction_f.objects.all().values('event_name').annotate(total=Count('event_name'))
        web_activity_data_ga = Interaction_ga.objects.all().values('event_name').annotate(total=Sum('event_count'))
        web_activity_data = list(web_activity_data_file) + list(web_activity_data_ga)
        if (len(web_activity_data)):
            web_activity_data = pd.DataFrame(web_activity_data).groupby(['event_name'], as_index=False).sum().to_dict('r')
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
                'title': 'Statistiques d’activités Web par types',
                'data': web_activity_report,
                'type': 'pie',
            },
            {
                'id': 'event-chart',
                'title': 'Statistiques d’événements par types',
                'data': event_report,
                'type': 'column'
            },
            {
                'id': 'product-chart',
                'title': 'Statistiques d’articles par types',
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
def mapping_data(data, template, source_name):
    try:
        total = 0   # Total object rows in imported data
        count = 0   # Total object rows saved in database
        if isinstance(data, list):
            total = len(data)
            # Store history of import
            import_info = ImportInfo(table_name=template['model_name'], source_name=source_name)
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
            list_required_attributes = ['event_date', 'event_timestamp', 'items', 'event_name', 'device', 'geo', 'user_id', 'traffic_source']
            list_required_event_params = ['ga_session_id', 'page_title', 'page_location']
            for obj in json_data:
                new_obj = {}
                for attribute in list_required_attributes:
                    if attribute == 'event_date':
                        date = pydash.get(obj, attribute)
                        format_date = date[:4] + '-' + date[4:6] + '-' + date[6:8]
                        new_obj[attribute] = format_date
                    elif attribute == 'event_timestamp':
                        new_obj[attribute] = int(pydash.get(obj, attribute))
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
                            
                for item in new_obj['items']:
                    item['item_eventname'] = new_obj['event_name']
                reformated_json_data.append(new_obj)
        elif (item_type == 'google-analytic' and template_type == 'default'):
            list_required_attributes = ['date', 'eventName', 'deviceCategory', 'country', 'pageLocation', 'eventCount', 'sessions', 'operatingSystem', 'browser']
            for obj in json_data:
                new_obj = {}
                for attribute in list_required_attributes:
                    if attribute == 'date':
                        date = pydash.get(obj, attribute)
                        format_date = date[:4] + '-' + date[4:6] + '-' + date[6:8]
                        new_obj[attribute] = format_date
                    else:
                        new_obj[attribute] = pydash.get(obj, attribute)
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
        mapping_result = mapping_data(json_data, template, file.name)
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
        mapping_result = mapping_data(response_data, mapping_template, url)

        return Response(mapping_result, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


@api_view(['GET'])
def get_import_info(request, item_type):
    try:
        tables = {
            "event": "events",
            "article": "products",
            "web-activity": "interaction_f",
            "google-analytic-report": "interaction_ga",
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
            "event": ["events", "businessentity", "entityeventrole", "eventdate"],
            "article": ["products", "businessentity", "entityproductrole"],
            "web-activity": ["interaction_f"],
            "google-analytic-report": ["interaction_ga"]
        }

        for table in tables[item_type]:
            Model = apps.get_model(app_label='dimadb', model_name=table)
            Model.objects.filter(import_id=pk).delete()
        ImportInfo.objects.filter(id=pk).delete()
        
        return Response({}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})


# Generate recommend api to retrieve recommendation
def generate_recommend_api(level, item_type, recommend_type, quantity, domain, item_url):
    api = IP_DOMAIN + '/dimadb/get-list-recommend/?'
    api += 'itemType=' + item_type
    api += '&level=' + level
    api += '&quantity=' + quantity

    if (recommend_type):
        api += '&recommendType=' + recommend_type
    if (domain):
        api += '&domain=' + domain
    if (item_url):
        api += '&itemUrl=' + item_url

    return api


recommend_display_fields = {
            'events': ['event_id', 'event_name', 'event_type', 'next_date', 'url', 'img', 'location_name'],
            'products': ['product_id', 'product_name', 'product_type', 'url', 'img']
        }

# Get upcoming recommendation
def get_upcoming(table_name, quantity=1, domain=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    display_fields = recommend_display_fields[table_name]
    list_recommend_items = []
    filter_params = {}

    if (domain is not None):
        if (table_name == 'events'):
            filter_params['event_type'] = domain
        elif (table_name == 'products'):
            filter_params['product_type'] = domain

    list_objs = Model.objects.filter(Q(**filter_params))
    list_objs = [model_to_dict(obj) for obj in list(list_objs)]
    
    if (table_name == 'events'):
        list_filtered_obj = []
        today = datetime.today()
        EventDateModel = apps.get_model(app_label='dimadb', model_name='eventdate')
        for obj in list_objs:
            list_event_dates = EventDateModel.objects.filter(event_id=obj['id'], date__gte=today).order_by('date')
            list_event_dates = [model_to_dict(obj) for obj in list(list_event_dates)]
            if (len(list_event_dates)):
                obj['next_date'] = list_event_dates[0]['date']
                list_filtered_obj.append(obj)
        if (len(list_filtered_obj)):   
            list_objs = sorted(list_filtered_obj, key=lambda x: x['next_date'])
        else:
            list_objs = []
        
    for i in range(0, int(quantity)):
        if (i < len(list_objs)):
            obj = list_objs[i]
            recommend_item = {}
            for field in list(display_fields):
                recommend_item[field] = obj[field]
            list_recommend_items.append(recommend_item)

    return list_recommend_items

# Get most popular recommendation
def order_by_score(table_name, list_objs):
    if (len(list_objs)): 
        list_interactions_f = Interaction_f.objects.filter(page_location__in=[obj['url'] for obj in list_objs])
        list_interactions_f = [model_to_dict(obj) for obj in list_interactions_f]
        if (len(list_interactions_f)):
            list_interactions_f = pd.DataFrame(list_interactions_f).groupby(['page_location', 'event_name'], as_index=False)['id'].count().rename(columns={'id':'event_count'}).to_dict('r')
        
        list_interactions_ga = list(Interaction_ga.objects.filter(page_location__in=[obj['url'] for obj in list_objs]).values('page_location', 'event_name', 'event_count'))
        list_interactions = list_interactions_f + list_interactions_ga
        if (len(list_interactions)):
            list_interactions = pd.DataFrame(list_interactions).groupby(['page_location', 'event_name'], as_index=False).sum().to_dict('r')
    
    list_objs_weight = {}
    for interaction in list_interactions:
        page_location = interaction['page_location']
        event_name = interaction['event_name']
        event_count = interaction['event_count']
        activity_weight = 0
        try:
            activity_type_info = model_to_dict(WebActivityType.objects.get(name=event_name)) 
            activity_weight = activity_type_info['value']       
        except:
            activity_weight = 1
        if page_location not in list_objs_weight:
            list_objs_weight[page_location] = 0
        list_objs_weight[page_location] += event_count * activity_weight

    
    for obj in list_objs:
        if obj['url'] in list_objs_weight: 
            obj['popular_score'] = list_objs_weight[obj['url']]
        else:
            obj['popular_score'] = 0
    if (len(list_objs)):   
        list_objs = sorted(list_objs, key=lambda d: d['popular_score'], reverse=True)
    else:
        list_objs = []
    return list_objs

# Get most popular recommendation
def get_most_popular(table_name, quantity=1, domain=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    display_fields = recommend_display_fields[table_name]
    list_recommend_items = []
    filter_params = {}
    list_interactions = []

    if (domain is not None):
        if (table_name == 'events'):
            filter_params['event_type'] = domain
        elif (table_name == 'products'):
            filter_params['product_type'] = domain

    list_objs = Model.objects.filter(Q(**filter_params))
    list_objs = [model_to_dict(obj) for obj in list(list_objs)]
    # list_objs = order_by_score(table_name, list_objs)
    
    if (table_name == 'events'):
        list_filtered_obj = []
        today = datetime.today()
        EventDateModel = apps.get_model(app_label='dimadb', model_name='eventdate')
        for obj in list_objs:
            list_event_dates = EventDateModel.objects.filter(event_id=obj['id'], date__gte=today).order_by('date')
            list_event_dates = [model_to_dict(obj) for obj in list(list_event_dates)]
            if (len(list_event_dates)):
                obj['next_date'] = list_event_dates[0]['date']
                list_filtered_obj.append(obj)
        if (len(list_filtered_obj)):        
            list_objs = sorted(list_filtered_obj, key=lambda x: x['next_date'])
        else:
            list_objs = []
        
    list_objs = order_by_score(table_name, list_objs)
    # if (len(list_objs)): 
    #     list_interactions_f = Interaction_f.objects.filter(page_location__in=[obj['url'] for obj in list_objs])
    #     list_interactions_f = [model_to_dict(obj) for obj in list_interactions_f]
    #     if (len(list_interactions_f)):
    #         list_interactions_f = pd.DataFrame(list_interactions_f).groupby(['page_location', 'event_name'], as_index=False)['id'].count().rename(columns={'id':'event_count'}).to_dict('r')
        
    #     list_interactions_ga = list(Interaction_ga.objects.filter(page_location__in=[obj['url'] for obj in list_objs]).values('page_location', 'event_name', 'event_count'))
    #     list_interactions = list_interactions_f + list_interactions_ga
    #     if (len(list_interactions)):
    #         list_interactions = pd.DataFrame(list_interactions).groupby(['page_location', 'event_name'], as_index=False).sum().to_dict('r')
    
    # list_objs_weight = {}
    # for interaction in list_interactions:
    #     page_location = interaction['page_location']
    #     event_name = interaction['event_name']
    #     event_count = interaction['event_count']
    #     activity_weight = 0
    #     try:
    #         activity_type_info = model_to_dict(WebActivityType.objects.get(name=event_name)) 
    #         activity_weight = activity_type_info['value']       
    #     except:
    #         activity_weight = 1
    #     if page_location not in list_objs_weight:
    #         list_objs_weight[page_location] = 0
    #     list_objs_weight[page_location] += event_count * activity_weight

    
    # for obj in list_objs:
    #     if obj['url'] in list_objs_weight: 
    #         obj['popular_score'] = list_objs_weight[obj['url']]
    #     else:
    #         obj['popular_score'] = 0
    # if (len(list_objs)):   
    #     list_objs = sorted(list_objs, key=lambda d: d['popular_score'], reverse=True)
    # else:
    #     list_objs = []
    
    for i in range(0, int(quantity)):
        if (i < len(list_objs)):
            obj = list_objs[i]
            recommend_item = {}
            for field in list(display_fields):
                recommend_item[field] = obj[field]
            recommend_item['popular_score'] = obj['popular_score']
            list_recommend_items.append(recommend_item)
            
    if (len(list_recommend_items) == 0):
        list_recommend_items = get_upcoming(table_name, quantity)
    return list_recommend_items


# Get similarity recommendation
def get_similar(table_name, quantity=1, item_url=None, recommend_type=None):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    display_fields = recommend_display_fields[table_name]
    list_recommend_items = []
    item_id = Model.objects.get(url=item_url).id
    list_similar_items = ContentBasedRecommender.recommend_items_by_items(table_name=table_name, items_id=item_id)
    
    if (table_name == 'events'):
        list_filtered_obj = []
        today = datetime.today()
        EventDateModel = apps.get_model(app_label='dimadb', model_name='eventdate')
        for obj in list_similar_items:
            list_event_dates = EventDateModel.objects.filter(event_id=obj['id'], date__gte=today).order_by('date')
            list_event_dates = [model_to_dict(obj) for obj in list(list_event_dates)]
            if (len(list_event_dates)):
                obj['next_date'] = list_event_dates[0]['date']
                list_filtered_obj.append(obj)
        if (len(list_filtered_obj)):        
            list_similar_items = sorted(list_filtered_obj, key=lambda x: x['similarity_score'], reverse=True)
        else:
            list_similar_items = []
    
    if (recommend_type == 'Similar combined with Most popular'):
        list_similar_items = order_by_score(table_name, list_similar_items)

    for i in range(0, int(quantity)):
        if (i < len(list_similar_items)):
            similar_obj = list_similar_items[i]
            obj = Model.objects.get(id=similar_obj['id'])
            obj = model_to_dict(obj)
            recommend_item = {}
            for field in list(display_fields):
                if field in obj:
                    recommend_item[field] = obj[field]
            if (table_name == 'events'):
                recommend_item['next_date'] = similar_obj['next_date']
            if (recommend_type == 'Similar combined with Most popular'):
                recommend_item['popular_score'] = similar_obj['popular_score']
            recommend_item['similarity_score'] = similar_obj['similarity_score']
            list_recommend_items.append(recommend_item)
            
    if (len(list_recommend_items) == 0):
        list_recommend_items = get_upcoming(table_name, quantity)

    return list_recommend_items
    
    
# Get list of recommend items
def get_recommend_items(level, item_type, recommend_type, quantity, domain, item_url):
    list_recommend_items = []

    if (level == 'Homepage'):
        if (recommend_type == 'Upcoming'):
            if (item_type == 'events'):
                list_recommend_items = get_upcoming(table_name=item_type, quantity=quantity)
        if (recommend_type == 'Most popular'):
            if (item_type == 'events'):
                list_recommend_items = get_most_popular(table_name=item_type, quantity=quantity)
            elif (item_type == 'products'):
                list_recommend_items = get_most_popular(table_name=item_type, quantity=quantity)
    elif (level == 'Domain'):
        if (recommend_type == 'Upcoming'):
            if (item_type == 'events'):
                list_recommend_items = get_upcoming(table_name=item_type, quantity=quantity, domain=domain)
        if (recommend_type == 'Most popular'):
            if (item_type == 'events'):
                list_recommend_items = get_most_popular(table_name=item_type, quantity=quantity, domain=domain)
            elif (item_type == 'products'):
                list_recommend_items = get_most_popular(table_name=item_type, quantity=quantity, domain=domain)
    else:
        if (item_type == 'events'):
            list_recommend_items = get_similar(table_name=item_type, quantity=quantity, item_url=item_url, recommend_type=recommend_type)
        elif (item_type == 'products'):
            list_recommend_items = get_similar(table_name=item_type, quantity=quantity, item_url=item_url, recommend_type=recommend_type)

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
            item_url = request.GET.get('itemUrl', None)
            list_recommend_items = get_recommend_items(level, item_type, recommend_type, quantity, domain, item_url)
            return Response({'itemType': item_type, 'recommendType': recommend_type, 'items': list_recommend_items}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Authorization failed'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as error:
        return Response({'message': error})

def get_embedded_link(api, recommend_type, is_gui=False):
    recommendItems = ''
    if (recommend_type == 'Upcoming'):
        recommendItems = 'upComingItems'
    elif (recommend_type == 'Most popular'):
        recommendItems = 'popularItems'
    elif (recommend_type == 'Similar'):
        recommendItems = 'similarItems'
    elif (recommend_type == 'Similar combined with Most popular'):
        recommendItems = 'popularSimilarItems'
    else:
        recommendItems = 'upComingItems'
        
    embedded_link = ''
    css_link = '<link rel="stylesheet" href="' + IP_DOMAIN + '/static/dimadb/css/recommender.css">'
    div_link = '<div id="' + recommendItems + '"></div>'
    js_link = '<script src="' + IP_DOMAIN + '/static/dimadb/js/recommender.js' + '"></script>'
    recommend_link = '<script>' + '\n'
    recommend_link += '\tvar ' + recommendItems + ' = getRecommend("' + api + '", "' + API_KEY + '");' + '\n'
    recommend_link += '\t' + recommendItems +'.then(res => {' + '\n'
    recommend_link += '\t\t//Handle recommend items here' + '\n'
    if (is_gui):
        recommend_link += '\t\t//Below code shows recommendation GUI' + '\n'
        recommend_link += '\t\tgetListView("' + recommendItems + '", res);' + '\n'
    else:
        recommend_link += '\t\t//Below code shows recommendation results' + '\n'
        recommend_link += '\t\tconsole.log(res);' + '\n'
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
        item_url = body['itemUrl']
        #Get recommend api + recommend list
        api = generate_recommend_api(level, item_type, recommend_type, quantity, domain, item_url)
        list_recommend_items = get_recommend_items(level, item_type, recommend_type, quantity, domain, item_url)
        embedded_links = [
            {
                "name": "Script dynamique et intégré dans chaque page (sans la génération des interfaces)",
                "link": get_embedded_link(api, recommend_type, is_gui=False),
            }, {
                "name": "Script dynamique et intégré dans chaque page (avec la génération des interfaces)",
                "link":  get_embedded_link(api, recommend_type, is_gui=True),
            }
        ]
        
        return Response({
            'items': list_recommend_items, 
            'api': api, 'apiKey': API_KEY, 
            'embeddedDynamicLinks': embedded_links, 
            }, status=status.HTTP_200_OK)
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
        # Recommend info
        # recommend_levels = {
        #     "Homepage": ["Upcoming", "Most popular"],
        #     "Domain": ["Upcoming", "Most popular"],
        #     "Item": ["Similar", "Similar combined with Most popular"]
        # }
        recommend_types = [
            {
                "name": "Upcoming",
                "displayName": "À venir"
            }, {
                "name": "Most popular",
                "displayName": "Les plus populaires"
            }, {
                "name": "Similar",
                "displayName": "Produits similaires"
            }, {
                "name": "Similar combined with Most popular",
                "displayName": "Produits similaires combinés avec les plus populaires"
            }
        ]
        
        recommend_levels = {
            "Homepage": {
                "displayName": "Page d'accueil",
                "algorithms": [recommend_types[0], recommend_types[1]]
            }, 
            "Domain": {
                "displayName": "Domaine",
                "algorithms": [recommend_types[0], recommend_types[1]]
            }, 
            "Item": {
                "displayName": "Produit",
                "algorithms": [recommend_types[2], recommend_types[3]]
            }
        }
        
        # Get list domain(item_type)
        event_snippets = Events.objects.all()
        event_serializer = EventSerializer(event_snippets, many=True)
        event_types = Events.objects.values('event_type').distinct()
        event_types = [item['event_type'] for item in list(event_types)]

        article_snippets = Products.objects.all()
        article_serializer = ArticleSerializer(article_snippets, many=True)
        article_types = Products.objects.values('product_type').distinct()
        article_types = [item['product_type'] for item in list(article_types)]
        
        list_item_infos = {
            "events": {
                "name": "Événements",
                "items": event_serializer.data,
                "types": event_types
            },
            "products": {
                "name": "Articles",
                "items": article_serializer.data,
                "types": article_types
            }    
        }
        
        embedded_links = [
            {
                 "name": "Script fixé et intégré dans la page d'accueil (sans la génération des interfaces)",
                "link":  get_embedded_recommendation(is_gui=False),
            }, 
            {
                 "name": "Script fixé et intégré dans la page d'accueil (avec la génération des interfaces)",
                "link":  get_embedded_recommendation(is_gui=True)
            }
        ]

        return Response({'embeddedFixedLinks': embedded_links,
                         'recommendLevels': recommend_levels,
                         'listItemInfos': list_item_infos}, status=status.HTTP_200_OK)
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
        web_activity_types_f = Interaction_f.objects.values('event_name').distinct()
        web_activity_types_f = [item['event_name'] for item in list(web_activity_types_f)]
        web_activity_types_ga = Interaction_ga.objects.values('event_name').distinct()
        web_activity_types_ga = [item['event_name'] for item in list(web_activity_types_ga)]
        web_activity_types = list(dict.fromkeys(web_activity_types_f + web_activity_types_ga))
        existed_web_activity_types = WebActivityType.objects.values('name').distinct()
        existed_web_activity_types = [item['name'] for item in list(existed_web_activity_types)]
        web_activity_types = web_activity_types + existed_web_activity_types
        web_activity_types = list(dict.fromkeys(web_activity_types))
        web_activity_types = [type for type in web_activity_types if type in ['user_engagement', 'scroll', 'page_view']]
        
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
        
        #Session
        if (group_type == 'none'):
            sessions_file = Interaction_f.objects.filter(
                visit_date__range=[start_date, end_date]).values('session_id').distinct().count()
            sessions_ga = Interaction_ga.objects.filter(
                date__range=[start_date, end_date]).aggregate(Sum('session_count'))['session_count__sum'] or 0
            sessions = [{'type': 'all', 'sum': sessions_file + sessions_ga}]
        elif (group_type == 'daily'):
            sessions_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date')).annotate(sum=Count('session_id', distinct=True))
            sessions_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).values(
                day=F('date')).annotate(sum=Sum('session_count'))
            sessions = list(sessions_file) + list(sessions_ga)
            if (len(sessions)):
                sessions = pd.DataFrame(sessions).groupby(['day'], as_index=False).sum().to_dict('r')
                sessions = sorted(sessions, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            sessions_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week').annotate(sum=Count('session_id', distinct=True))
            sessions_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week').annotate(sum=Sum('session_count'))
            sessions = list(sessions_file) + list(sessions_ga)
            if (len(sessions)):
                sessions = pd.DataFrame(sessions).groupby(['week'], as_index=False).sum().to_dict('r')
                sessions = sorted(sessions, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            sessions_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month').annotate(sum=Count('session_id', distinct=True))
            sessions_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month').annotate(sum=Sum('session_count'))
            sessions = list(sessions_file) + list(sessions_ga)
            if (len(sessions)):
                sessions = pd.DataFrame(sessions).groupby(['month'], as_index=False).sum().to_dict('r')
                sessions = sorted(sessions, key=lambda k : k['month'])
        else:
            sessions_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year').annotate(sum=Count('session_id', distinct=True))
            sessions_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year').annotate(sum=Sum('session_count'))
            sessions = list(sessions_file) + list(sessions_ga)
            if (len(sessions)):
                sessions = pd.DataFrame(sessions).groupby(['year'], as_index=False).sum().to_dict('r')
                sessions = sorted(sessions, key=lambda k : k['year'])
        reports.append(create_report('session_report', 'Statistiques de sessions Web',
                        sessions, 'column', group_type == 'none'))

        # Web_activities:
        if (group_type == 'none'):
            web_activities_file = Interaction_f.objects.filter(
                visit_date__range=[start_date, end_date]).all().count()
            web_activities_ga = Interaction_ga.objects.filter(
                date__range=[start_date, end_date]).aggregate(Sum('event_count'))['event_count__sum'] or 0
            web_activities = [{'type': 'all', 'sum': web_activities_file + web_activities_ga}]
        elif (group_type == 'daily'):
            web_activities_file = Interaction_f.objects.filter(visit_date__range=[
                                                        start_date, end_date]).values(day=F('visit_date')).annotate(sum=Count('id'))
            web_activities_ga = Interaction_ga.objects.filter(date__range=[
                                                        start_date, end_date]).values(day=F('date')).annotate(sum=Sum('event_count'))
            web_activities = list(web_activities_file) + list(web_activities_ga)
            if (len(web_activities)):
                web_activities = pd.DataFrame(web_activities).groupby(['day'], as_index=False).sum().to_dict('r')
                web_activities = sorted(web_activities, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            web_activities_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week').annotate(sum=Count('id'))
            web_activities_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week').annotate(sum=Sum('event_count'))
            web_activities = list(web_activities_file) + list(web_activities_ga)
            if (len(web_activities)):
                web_activities = pd.DataFrame(web_activities).groupby(['week'], as_index=False).sum().to_dict('r')
                web_activities = sorted(web_activities, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            web_activities_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month').annotate(sum=Count('id'))
            web_activities_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month').annotate(sum=Sum('event_count'))
            web_activities = list(web_activities_file) + list(web_activities_ga)
            if (len(web_activities)):
                web_activities = pd.DataFrame(web_activities).groupby(['month'], as_index=False).sum().to_dict('r')
                web_activities = sorted(web_activities, key=lambda k : k['month'])
        else:
            web_activities_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year').annotate(sum=Count('id'))
            web_activities_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year').annotate(sum=Sum('event_count'))
            web_activities = list(web_activities_file) + list(web_activities_ga)
            if (len(web_activities)):
                web_activities = pd.DataFrame(web_activities).groupby(['year'], as_index=False).sum().to_dict('r')
                web_activities = sorted(web_activities, key=lambda k : k['year'])
        reports.append(create_report('web_activities_report',
                        'Statistiques d’activités Web', web_activities, 'column', group_type == 'none'))

        # Web Activities device_category:
        if (group_type == 'none'):
            web_activities_device_file = Interaction_f.objects.filter(visit_date__range=[
                                                               start_date, end_date]).values(type=F('device_category')).annotate(sum=Count('id'))
            web_activities_device_ga = Interaction_ga.objects.filter(date__range=[
                                                                start_date, end_date]).values(type=F('device_category')).annotate(sum=Sum('event_count'))
            web_activities_device = list(web_activities_device_file) + list(web_activities_device_ga)
            if (len(web_activities_device)):
                web_activities_device = pd.DataFrame(web_activities_device).groupby(['type'], as_index=False).sum().to_dict('r')
        elif (group_type == 'daily'):
            web_activities_device_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('device_category')).annotate(sum=Count('id'))
            web_activities_device_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).values(
                day=F('date'), type=F('device_category')).annotate(sum=Sum('event_count'))
            web_activities_device = list(web_activities_device_file) + list(web_activities_device_ga)
            if (len(web_activities_device)):
                web_activities_device = pd.DataFrame(web_activities_device).groupby(['day', 'type'], as_index=False).sum().to_dict('r')
                web_activities_device = sorted(web_activities_device, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            web_activities_device_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('device_category')).annotate(sum=Count('id'))
            web_activities_device_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week', type=F('device_category')).annotate(sum=Sum('event_count'))
            web_activities_device = list(web_activities_device_file) + list(web_activities_device_ga)
            if (len(web_activities_device)):
                web_activities_device = pd.DataFrame(web_activities_device).groupby(['week', 'type'], as_index=False).sum().to_dict('r')
                web_activities_device = sorted(web_activities_device, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            web_activities_device_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('device_category')).annotate(sum=Count('id'))
            web_activities_device_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month', type=F('device_category')).annotate(sum=Sum('event_count'))
            web_activities_device = list(web_activities_device_file) + list(web_activities_device_ga)
            if (len(web_activities_device)):
                web_activities_device = pd.DataFrame(web_activities_device).groupby(['month', 'type'], as_index=False).sum().to_dict('r')
                web_activities_device = sorted(web_activities_device, key=lambda k : k['month'])
        else:
            web_activities_device_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('device_category')).annotate(sum=Count('id'))
            web_activities_device_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year', type=F('device_category')).annotate(sum=Sum('event_count'))
            web_activities_device = list(web_activities_device_file) + list(web_activities_device_ga)
            if (len(web_activities_device)):
                web_activities_device = pd.DataFrame(web_activities_device).groupby(['year', 'type'], as_index=False).sum().to_dict('r')
                web_activities_device = sorted(web_activities_device, key=lambda k : k['year'])
        reports.append(create_report('session_device_report', 'Statistiques d’activités Web par types d’appareils',
                        web_activities_device, 'column', group_type == 'none'))

        # Web Activities browser:
        if (group_type == 'none'):
            web_activities_browser_file = Interaction_f.objects.filter(visit_date__range=[
                                                               start_date, end_date]).values(type=F('browser')).annotate(sum=Count('id'))
            web_activities_browser_ga = Interaction_ga.objects.filter(date__range=[
                                                                start_date, end_date]).values(type=F('browser')).annotate(sum=Sum('event_count'))
            web_activities_browser = list(web_activities_browser_file) + list(web_activities_browser_ga)
            if (len(web_activities_browser)):
                web_activities_browser = pd.DataFrame(web_activities_browser).groupby(['type'], as_index=False).sum().to_dict('r')
        elif (group_type == 'daily'):
            web_activities_browser_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('browser')).annotate(sum=Count('id'))
            web_activities_browser_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).values(
                day=F('date'), type=F('browser')).annotate(sum=Sum('event_count'))
            web_activities_browser = list(web_activities_browser_file) + list(web_activities_browser_ga)
            if (len(web_activities_browser)):
                web_activities_browser = pd.DataFrame(web_activities_browser).groupby(['day', 'type'], as_index=False).sum().to_dict('r')
                web_activities_browser = sorted(web_activities_browser, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            web_activities_browser_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('browser')).annotate(sum=Count('id'))
            web_activities_browser_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week', type=F('browser')).annotate(sum=Sum('event_count'))
            web_activities_browser = list(web_activities_browser_file) + list(web_activities_browser_ga)
            if (len(web_activities_browser)):
                web_activities_browser = pd.DataFrame(web_activities_browser).groupby(['week', 'type'], as_index=False).sum().to_dict('r')
                web_activities_browser = sorted(web_activities_browser, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            web_activities_browser_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('browser')).annotate(sum=Count('id'))
            web_activities_browser_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month', type=F('browser')).annotate(sum=Sum('event_count'))
            web_activities_browser = list(web_activities_browser_file) + list(web_activities_browser_ga)
            if (len(web_activities_browser)):
                web_activities_browser = pd.DataFrame(web_activities_browser).groupby(['month', 'type'], as_index=False).sum().to_dict('r')
                web_activities_browser = sorted(web_activities_browser, key=lambda k : k['month'])
        else:
            web_activities_browser_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('browser')).annotate(sum=Count('id'))
            web_activities_browser_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year', type=F('browser')).annotate(sum=Sum('event_count'))
            web_activities_browser = list(web_activities_browser_file) + list(web_activities_browser_ga)
            if (len(web_activities_browser)):
                web_activities_browser = pd.DataFrame(web_activities_browser).groupby(['year', 'type'], as_index=False).sum().to_dict('r')
                web_activities_browser = sorted(web_activities_browser, key=lambda k : k['year'])
        reports.append(create_report('session_browser_report', 'Statistiques d’activités Web par navigateurs Web',
                        web_activities_browser, 'column', group_type == 'none'))

        # Web Activities os:
        if (group_type == 'none'):
            web_activities_os_file = Interaction_f.objects.filter(visit_date__range=[
                                                               start_date, end_date]).values(type=F('operating_system')).annotate(sum=Count('id'))
            web_activities_os_ga = Interaction_ga.objects.filter(date__range=[
                                                                start_date, end_date]).values(type=F('operating_system')).annotate(sum=Sum('event_count'))
            web_activities_os = list(web_activities_os_file) + list(web_activities_os_ga)
            if (len(web_activities_os)):
                web_activities_os = pd.DataFrame(web_activities_os).groupby(['type'], as_index=False).sum().to_dict('r')
        elif (group_type == 'daily'):
            web_activities_os_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('operating_system')).annotate(sum=Count('id'))
            web_activities_os_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).values(
                day=F('date'), type=F('operating_system')).annotate(sum=Sum('event_count'))
            web_activities_os = list(web_activities_os_file) + list(web_activities_os_ga)
            if (len(web_activities_os)):
                web_activities_os = pd.DataFrame(web_activities_os).groupby(['day', 'type'], as_index=False).sum().to_dict('r')
                web_activities_os = sorted(web_activities_os, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            web_activities_os_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('operating_system')).annotate(sum=Count('id'))
            web_activities_os_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week', type=F('operating_system')).annotate(sum=Sum('event_count'))
            web_activities_os = list(web_activities_os_file) + list(web_activities_os_ga)
            if (len(web_activities_os)):
                web_activities_os = pd.DataFrame(web_activities_os).groupby(['week', 'type'], as_index=False).sum().to_dict('r')
                web_activities_os = sorted(web_activities_os, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            web_activities_os_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('operating_system')).annotate(sum=Count('id'))
            web_activities_os_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month', type=F('operating_system')).annotate(sum=Sum('event_count'))
            web_activities_os = list(web_activities_os_file) + list(web_activities_os_ga)
            if (len(web_activities_os)):
                web_activities_os = pd.DataFrame(web_activities_os).groupby(['month', 'type'], as_index=False).sum().to_dict('r')
                web_activities_os = sorted(web_activities_os, key=lambda k : k['month'])
        else:
            web_activities_os_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('operating_system')).annotate(sum=Count('id'))
            web_activities_os_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year', type=F('operating_system')).annotate(sum=Sum('event_count'))
            web_activities_os = list(web_activities_os_file) + list(web_activities_os_ga)
            if (len(web_activities_os)):
                web_activities_os = pd.DataFrame(web_activities_os).groupby(['year', 'type'], as_index=False).sum().to_dict('r')
                web_activities_os = sorted(web_activities_os, key=lambda k : k['year'])
        reports.append(create_report('session_os_report', 'Statistiques d’activités Web par systèmes d’exploitation',
                        web_activities_os, 'column', group_type == 'none'))

        # Web Activities type:
        if (group_type == 'none'):
            web_activities_type_file = Interaction_f.objects.filter(visit_date__range=[
                                                               start_date, end_date]).values(type=F('event_name')).annotate(sum=Count('id'))
            web_activities_type_ga = Interaction_ga.objects.filter(date__range=[
                                                                start_date, end_date]).values(type=F('event_name')).annotate(sum=Sum('event_count'))
            web_activities_type = list(web_activities_type_file) + list(web_activities_type_ga)
            if (len(web_activities_type)):
                web_activities_type = pd.DataFrame(web_activities_type).groupby(['type'], as_index=False).sum().to_dict('r')
        elif (group_type == 'daily'):
            web_activities_type_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).values(
                day=F('visit_date'), type=F('event_name')).annotate(sum=Count('id'))
            web_activities_type_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).values(
                day=F('date'), type=F('event_name')).annotate(sum=Sum('event_count'))
            web_activities_type = list(web_activities_type_file) + list(web_activities_type_ga)
            if (len(web_activities_type)):
                web_activities_type = pd.DataFrame(web_activities_type).groupby(['day', 'type'], as_index=False).sum().to_dict('r')
                web_activities_type = sorted(web_activities_type, key=lambda k : k['day'])
        elif (group_type == 'weekly'):
            web_activities_type_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                week=TruncWeek('visit_date')).values('week', type=F('event_name')).annotate(sum=Count('id'))
            web_activities_type_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                week=TruncWeek('date')).values('week', type=F('event_name')).annotate(sum=Sum('event_count'))
            web_activities_type = list(web_activities_type_file) + list(web_activities_type_ga)
            if (len(web_activities_type)):
                web_activities_type = pd.DataFrame(web_activities_type).groupby(['week', 'type'], as_index=False).sum().to_dict('r')
                web_activities_type = sorted(web_activities_type, key=lambda k : k['week'])
        elif (group_type == 'monthly'):
            web_activities_type_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                month=TruncMonth('visit_date')).values('month', type=F('event_name')).annotate(sum=Count('id'))
            web_activities_type_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                month=TruncMonth('date')).values('month', type=F('event_name')).annotate(sum=Sum('event_count'))
            web_activities_type = list(web_activities_type_file) + list(web_activities_type_ga)
            if (len(web_activities_type)):
                web_activities_type = pd.DataFrame(web_activities_type).groupby(['month', 'type'], as_index=False).sum().to_dict('r')
                web_activities_type = sorted(web_activities_type, key=lambda k : k['month'])
        else:
            web_activities_type_file = Interaction_f.objects.filter(visit_date__range=[start_date, end_date]).annotate(
                year=TruncYear('visit_date')).values('year', type=F('event_name')).annotate(sum=Count('id'))
            web_activities_type_ga = Interaction_ga.objects.filter(date__range=[start_date, end_date]).annotate(
                year=TruncYear('date')).values('year', type=F('event_name')).annotate(sum=Sum('event_count'))
            web_activities_type = list(web_activities_type_file) + list(web_activities_type_ga)
            if (len(web_activities_type)):
                web_activities_type = pd.DataFrame(web_activities_type).groupby(['year', 'type'], as_index=False).sum().to_dict('r')
                web_activities_type = sorted(web_activities_type, key=lambda k : k['year'])
        reports.append(create_report('session_type_report', 'Statistiques d’activités Web par types d’activités',
                        web_activities_type, 'column', group_type == 'none'))

        return Response({'reports': reports}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})

def get_ga4_reports(view_id, json_key_file, start_date, end_date):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_key_file
    """Runs a simple report on a Google Analytics 4 property."""
    client = BetaAnalyticsDataClient()
    request = RunReportRequest(
        property=f"properties/{view_id}",
        dimensions=[Dimension(name=i) for i in dimensions],
        metrics=[Metric(name=i) for i in metrics],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )
    response = client.run_report(request)

    #Convert response to dataframe
    df = {}
    data = {}
    for row in response.rows:
        for idx, dimension in enumerate(row.dimension_values):
            dimension_name = dimensions[idx]
            if dimension_name not in df:
                df[dimension_name] = []
            df[dimension_name].append(dimension.value)
        for idx, metric in enumerate(row.metric_values):
            metric_name = metrics[idx]
            if metric_name not in df:
                df[metric_name] = []
            df[metric_name].append(metric.value)

    if df:
        data = pd.DataFrame(df)
    return data.to_dict('records')

def get_ua_reports(view_id, json_key_file, start_date, end_date):
    # Authenticate and construct service.
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
            json_key_file, scopes=[scope])
    service = build('analytics', 'v3', credentials=credentials)
    results = service.data().ga().get(
            ids='ga:' + view_id,
            start_date=start_date,
            end_date=end_date,
            metrics= ','.join(ua_metrics),
            dimensions= ','.join(ua_dimensions),
            include_empty_rows=True
            ).execute()
    
    #Convert response to dataframe
    df = []
    if ('rows' in results):
        df = results['rows']
    data = pd.DataFrame(df, columns=dimensions+metrics)
    return data.to_dict('records')

def get_google_analytic_reports(ga_version, view_id, json_key_file, start_date, end_date):
    if (ga_version == 'ga4'):
        return get_ga4_reports(view_id, json_key_file, start_date, end_date)
    elif (ga_version == 'ua'):
        return get_ua_reports(view_id, json_key_file, start_date, end_date)
    return [] 

@api_view(['GET'])
def get_synchronize_end_date(request):
    try:
        ga_version = dotenv.get_key(os.path.join(base_dir, '.env'), "GA_VERSION")
        ga_view_id = dotenv.get_key(os.path.join(base_dir, '.env'), "GA_VIEW_ID")
        ga_json_key_file = dotenv.get_key(os.path.join(base_dir, '.env'), "GA_JSON_KEY_FILE")
        list_ga_versions = [{'name': 'Google Analytics 4', 'value': 'ga4'}, 
                            {'name': 'Universal Analytics', 'value': 'ua'}]
        list_reports = list(Interaction_ga.objects.all())
        
        if (len(list_reports)):
            end_date = Interaction_ga.objects.latest('date').date + timedelta(days=1)
        else:
            end_date = '2022-01-01' 
        
        return Response({
                            'endDate': end_date, 
                            'listGAVersions': list_ga_versions,
                            'gaVersion': ga_version,
                            'gaViewID': ga_view_id,
                            'gaJSONKeyFile': ga_json_key_file}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})

@api_view(['POST'])
def synchronize_google_analytic(request):
    try:
        files = request.FILES.getlist('files[]')
        ga_version = request.POST.get('gaVersion')
        json_key_file_name = request.POST.get('jsonKeyFileName')
        view_id = request.POST.get('viewID')
        start_date = request.POST.get('startDate', date.today())
        end_date = request.POST.get('endDate', date.today())
        json_key_file = os.path.join(module_dir, 'configuration/', json_key_file_name)
        
        #Update new google analytics parameter
        if (len(files)):
            old_json_key_file = dotenv.get_key(os.path.join(base_dir, '.env'), "GA_JSON_KEY_FILE")
            if (old_json_key_file != ''):
                old_json_key_file_name = os.path.join(module_dir, 'configuration/', old_json_key_file)
                if default_storage.exists(old_json_key_file_name):
                    default_storage.delete(old_json_key_file_name)
            default_storage.save(json_key_file, files[0])
        
        dotenv.set_key(os.path.join(base_dir, '.env'), "GA_VERSION", ga_version)
        dotenv.set_key(os.path.join(base_dir, '.env'), "GA_VIEW_ID", view_id)
        dotenv.set_key(os.path.join(base_dir, '.env'), "GA_JSON_KEY_FILE", json_key_file_name)
        
        #Get data from google analytics
        reports = get_google_analytic_reports(ga_version, view_id, json_key_file, start_date, end_date)
        #Import data from google analytics to database
        item_type = 'google-analytic'
        template_type = 'default'
        json_data = reformated_data(reports, item_type, template_type)
        import_info = ImportInfo(table_name='interaction_ga', source_name=ga_version)
        import_info.save()
        
        for record in json_data:
            try:
                existed_reports = list(Interaction_ga.objects.filter(
                        event_name=record['eventName'],
                        date=record['date'],
                        operating_system=record['operatingSystem'],
                        device_category=record['deviceCategory'],
                        country=record['country'],
                        browser=record['browser'],
                        page_location=record['pageLocation']))
                # Check whether record exists in Interaction_ga table
                if (len(existed_reports)):
                    existed_report = existed_reports[0]
                    existed_report.session_count = record['sessions']
                    existed_report.event_count = record['eventCount']
                    existed_report.save()
                else:
                    new_report = Interaction_ga(
                        event_name=record['eventName'],
                        date=record['date'],
                        operating_system=record['operatingSystem'],
                        device_category=record['deviceCategory'],
                        country=record['country'],
                        browser=record['browser'],
                        page_location=record['pageLocation'],
                        event_count=record['eventCount'],
                        session_count=record['sessions'],
                        import_id=import_info.id
                    )
                    new_report.save()
            except:
                new_report = Interaction_ga(
                    event_name=record['eventName'],
                    date=record['date'],
                    operating_system=record['operatingSystem'],
                    device_category=record['deviceCategory'],
                    country=record['country'],
                    browser=record['browser'],
                    page_location=record['pageLocation'],
                    event_count=record['eventCount'],
                    session_count=record['sessions'],
                    import_id=import_info.id
                )
                new_report.save()
       
        return Response({}, status=status.HTTP_200_OK)
    except Exception as error:
        return Response({'message': error})
    
def get_embedded_recommendation(is_gui=False):
    embedded_link = ''
    css_link = '<link rel="stylesheet" href="' + IP_DOMAIN + '/static/dimadb/css/recommender.css">'
    div_link = '<div id="recommendations"></div>'
    js_link = '<script src="' + IP_DOMAIN + '/static/dimadb/js/recommender.js' + '"></script>'
    recommend_link = '<script>' + '\n'
    recommend_link += '\tvar recommendations = getRecommendation("' + IP_DOMAIN + '/dimadb/get-recommendation", "' + API_KEY + '");' + '\n'
    recommend_link += '\trecommendations.then(res => {' + '\n'
    recommend_link += '\t\t//Handle recommend items here' + '\n'
    if (is_gui):
        recommend_link += '\t\t//Below code shows recommendation GUI' + '\n'
        recommend_link += '\t\tgetListViews(res);' + '\n'
    else:
        recommend_link += '\t\t//Below code shows recommendation results' + '\n'
        recommend_link += '\t\tconsole.log(res);' + '\n'
    recommend_link += '\t});' + '\n'
    recommend_link += '</script>'
    embedded_link = css_link + '\n' + div_link + '\n' + js_link + '\n' + recommend_link
    
    return embedded_link

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_recommendation(request):
    try:
        # Authorization
        bearer_token = request.headers.get('Authorization')
        if (bearer_token == 'Bearer ' + API_KEY):
            # Read request info
            url = request.GET.get('url', None)
            url_parts = url.split('/')
            url_len = len(url_parts)
            recommendation = []
            item_type = ''
            item_url = ''
            slug_domain = ''
            item_domain = ''
            recommend_level = ''
            recommend_types = []
            
            #Mapping itemType, recommendLevel, domain with url
            for index, part in enumerate(url_parts):
                if part == 'magazine':
                    item_type = 'products'
                    if (url_len - index == 3):
                        recommend_level = 'Item'
                    elif (url_len - index == 2):
                        if url_parts[url_len-1] != 'tous-les-articles':
                            recommend_level = 'Domain'
                            slug_domain = url_parts[url_len-1]
                        else:
                            recommend_level = 'Homepage'
                    else:
                        recommend_level = 'Homepage'
                    break
                elif part == 'evenements':
                    item_type = 'events'
                    if (url_len - index == 2):
                        recommend_level = 'Item'
                    else:
                        recommend_level = 'Homepage'
                    break
            
            if (recommend_level == 'Item'):
                item_url = url
                recommend_types += ['Similar']
            elif (recommend_level == 'Homepage'):
                if (item_type == 'events'):
                    recommend_types += ['Upcoming']
                recommend_types += ['Most popular']
            elif (recommend_level == 'Domain'):
                if (item_type == 'events'):
                    recommend_types += ['Upcoming']
                recommend_types += ['Most popular']
                Model = apps.get_model(app_label='dimadb', model_name=item_type)
                domain_column = ''
                
                if (item_type == 'events'):
                    domain_column = 'event_type'
                else:
                    domain_column = 'product_type'
                item_domains = Model.objects.all().values(domain_column).distinct()
                item_domains = [domain[domain_column] for domain in list(item_domains)]
                
                for domain in item_domains:
                    if slugify(domain) == slug_domain:
                        item_domain = domain
                        break
                    
            # if (url == 'file:///Users/nguyenchannam/Desktop/test.html'):
            #     recommend_level = 'Item'
            #     item_type = 'events'
            #     recommend_types = ['Similar']
            #     item_url = 'https://dici.ca/evenements/helene-guilmaine-a-l-origine-les-deesses-meres'
                
            for recommend_type in recommend_types:
                recommends = get_recommend_items(recommend_level, item_type, recommend_type, 4, item_domain, item_url)
                recommendation.append({
                    'itemType': item_type,
                    'recommendType': recommend_type, 
                    'items': recommends})
            
            return Response(recommendation, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Authorization failed'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as error:
        return Response({'message': error})