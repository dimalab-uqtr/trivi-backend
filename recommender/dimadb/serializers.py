from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Events, Products, Interaction, ImportInfo

        
class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction
        fields = ('id', 'interaction_id', 'session_id', 'visit_date', 'event_name', 'operating_system', 'device_category', 'device_brand', 'browser', 'page_title', 'page_location')
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = ('id', 'event_id', 'event_name', 'event_title',
                  'event_type', 'start_date', 'end_date', 'next_date', 'status')
class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Products
        fields = ('id', 'product_id', 'product_name',
                  'product_price', 'product_revenue', 'status')
class ImportInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportInfo
        fields = '__all__'