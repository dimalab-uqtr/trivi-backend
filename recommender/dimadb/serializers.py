from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Events, Products, Interaction_f, ImportInfo

        
class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction_f
        fields = ('id', 'session_id', 'visit_date', 'event_name', 'page_title', 'page_location', 'operating_system', 'device_category', 'browser')
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = ('id', 'event_id', 'event_name', 'event_type', 'url')
class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Products
        fields = ('id', 'product_id', 'product_name', 'product_type', 'url')
class ImportInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportInfo
        fields = ('id', 'source_name', 'import_date')