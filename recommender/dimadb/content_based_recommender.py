from django.db.models.aggregates import Sum
from django.forms.models import model_to_dict
from .models import LdaSimilarity
from .lda_model_builder import LdaModelManager
from django.db.models import Q
from django.apps import apps

class ContentBasedRecommender():
    def __init__(self, min_sim=0.1):
        self.min_sim = min_sim
        
    @staticmethod
    def recommend_items_by_items(table_name, items_id):
        threshold = 0.8
        source_records = LdaSimilarity.objects.filter(source=items_id, item_type=table_name, similarity__gte=threshold)
        target_records = LdaSimilarity.objects.filter(target=items_id, item_type=table_name, similarity__gte=threshold)
        
        records = []
        records = records + [{'id': item.target, 'similarity_score': item.similarity} for item in list(source_records)]
        records = records + [{'id': item.source, 'similarity_score': item.similarity} for item in list(target_records)]
        
        new_records = []
        for record in records:
            Model = apps.get_model(app_label='dimadb', model_name=table_name)
            list_objs = Model.objects.filter(id=record['id'])
            list_objs = [model_to_dict(obj) for obj in list(list_objs)]
            if (len(list_objs)):
                obj = list_objs[0]
                obj['similarity_score'] = record['similarity_score']
                new_records.append(obj)
                
        new_records = sorted(new_records, key = lambda i: i['similarity_score'],reverse=True)
        return new_records
    
    @staticmethod
    def train_items_by_items(table_name):
        manager = LdaModelManager()
        manager.train_model(table_name=table_name)
        
        return