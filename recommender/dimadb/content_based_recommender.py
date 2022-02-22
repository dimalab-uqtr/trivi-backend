from django.db.models.aggregates import Sum
from django.forms.models import model_to_dict
from .models import LdaSimilarity
from .lda_model_builder import LdaModelManager
from django.db.models import Q

class ContentBasedRecommender():
    def __init__(self, min_sim=0.1):
        self.min_sim = min_sim
        
    @staticmethod
    def recommend_items_by_items(table_name, items_id):
        source_records = LdaSimilarity.objects.filter(source=items_id, item_type=table_name)
        target_records = LdaSimilarity.objects.filter(target=items_id, item_type=table_name)
        
        records = []
        records = records + [{'id': item.target, 'similarity': item.similarity} for item in list(source_records)]
        records = records + [{'id': item.source, 'similarity': item.similarity} for item in list(target_records)]
        records = sorted(records, key = lambda i: i['similarity'],reverse=True)
        return records
    
    @staticmethod
    def train_items_by_items(table_name):
        manager = LdaModelManager()
        manager.train_model(table_name=table_name)
        
        return