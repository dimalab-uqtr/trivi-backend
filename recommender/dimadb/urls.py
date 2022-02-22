from django.urls import path
from .views import *

urlpatterns = [
    path('home/', home),
    path('import-file/<item_type>/', import_json_file),
    path('import-api/<item_type>/', import_api),
    path('list-item/<item_type>/', ItemList.as_view()),
    path('get-item/<item_type>/<pk>/', ItemDetail.as_view()),
    path('get-recommend-api/', get_recommend_api),
    path('get-recommend-info/', get_recommend_info),
    path('get-configure-info/', get_configure_info),
    path('get-list-recommend/', get_list_recommend),
    path('get-import-info/<item_type>/', get_import_info),
    path('get-mapping-templates/<item_type>/', get_mapping_templates),
    path('get-reports/', get_reports),
    path('delete-multiple-items/<item_type>/<pk>/', delete_imported_items),
    path('train-similar-recommend/', train_similar_recommend),
    path('update-activity-weight/', update_activity_weight),
]
