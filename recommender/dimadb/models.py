from django.db import models
from django.contrib.auth.models import User

# Create your models here.



# DB for Machine Learning Model

class LdaSimilarityVersion(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    n_topics = models.IntegerField(null=True)
    item_type = models.CharField(max_length=150, null=True, blank=True)
    n_products = models.IntegerField(null=True)

    def __str__(self):
        return format(self.created_at)


class LdaSimilarity(models.Model):
    source = models.CharField(max_length=150, null=True, blank=True)
    target = models.CharField(max_length=150, null=True, blank=True)
    item_type = models.CharField(max_length=150, null=True, blank=True)
    similarity = models.DecimalField(max_digits=10, decimal_places=7)
    version = models.CharField(max_length=150, null=True, blank=True)


# Import_info:
class ImportInfo(models.Model):
    id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=50, null=True, blank=True)
    source_name = models.CharField(max_length=200, null=True, blank=True)
    import_date = models.DateTimeField(auto_now_add=True)

# New_event:
class Events(models.Model):
    id = models.AutoField(primary_key=True)
    event_id = models.CharField(max_length=150, unique=True)
    event_name = models.CharField(max_length=150, null=True, blank=True)
    event_title = models.CharField(max_length=150, null=True, blank=True)
    event_type = models.CharField(max_length=150, null=True, blank=True)
    event_price = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    price_type = models.CharField(max_length=50, null=True, blank=True)
    slug = models.CharField(max_length=150, null=True, blank=True)
    lang = models.CharField(max_length=150, null=True, blank=True)
    img = models.CharField(max_length=150, null=True, blank=True)
    url = models.CharField(max_length=150, null=True, blank=True)
    location_name = models.CharField(max_length=150, null=True, blank=True)
    location_address = models.CharField(max_length=150, null=True, blank=True)
    location_city = models.CharField(max_length=50, null=True, blank=True)
    location_state = models.CharField(max_length=50, null=True, blank=True)
    location_country = models.CharField(max_length=50, null=True, blank=True)
    location_zipcode = models.CharField(max_length=50, null=True, blank=True)
    is_public = models.CharField(max_length=10, choices=(
        ('True', True), ('False', False)), default='True')
    status = models.CharField(max_length=30, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)
    
class EventDate(models.Model):
    id = models.AutoField(primary_key=True)
    event_id = models.CharField(max_length=150, null=True, blank=True)
    date = models.DateTimeField(null=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)
    

# New_product:

class Products(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.CharField(max_length=150, unique=True)
    product_name = models.CharField(max_length=150, null=True, blank=True)
    product_type = models.CharField(max_length=150, choices=(('Musées','Musées'), ('Arts de la scène','Arts de la scène'), ('Littérature','Littérature'), ('Arts visuels','Arts visuels'), ('Arts médiatiques','Arts médiatiques'), ("Métiers d'art", "Métiers d'art"), ('Patrimoine','Patrimoine'), ('Autres','Autres')), default='Autres', null=True, blank=True)
    product_price = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    product_revenue = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    price_type = models.CharField(max_length=50, null=True, blank=True)
    is_public = models.CharField(max_length=10, choices=(
        ('True', True), ('False', False)), default='True')
    status = models.CharField(max_length=30, null=True, blank=True)
    slug = models.CharField(max_length=150, null=True, blank=True)
    img = models.CharField(max_length=150, null=True, blank=True)
    url = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)


# BusinessEntity

class BusinessEntity(models.Model):
    id = models.AutoField(primary_key=True)
    entity_id = models.CharField(max_length=50, null=True, blank=True)
    entity_name = models.CharField(max_length=50, null=True, blank=True)
    slug = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)


# EntityEventRole

class EntityEventRole(models.Model):
    id = models.AutoField(primary_key=True)
    entity_id = models.CharField(max_length=50, null=True, blank=True)
    event_id = models.CharField(max_length=50, null=True, blank=True)
    role_name = models.CharField(max_length=50, null=True, blank=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)
    
    
# EntityProductRole

class EntityProductRole(models.Model):
    id = models.AutoField(primary_key=True)
    entity_id = models.CharField(max_length=50, null=True, blank=True)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    role_name = models.CharField(max_length=50, null=True, blank=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)


# EventSimilarity

class EventSimilarity(models.Model):
    id = models.AutoField(primary_key=True)
    source_id = models.CharField(max_length=50, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True)
    similarity = models.DecimalField(max_digits=5, decimal_places=2)
    algo = models.CharField(max_length=50, null=True, blank=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)


# ProductSimilarity

class ProductSimilarity(models.Model):
    id = models.AutoField(primary_key=True)
    source_id = models.CharField(max_length=50, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True)
    similarity = models.DecimalField(max_digits=5, decimal_places=2)
    algo = models.CharField(max_length=50, null=True, blank=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)


# Interaction

class Interaction_f(models.Model):
    id = models.AutoField(primary_key=True)
    interaction_id = models.CharField(max_length=50, null=True, blank=True)
    session_id = models.CharField(max_length=50, null=True, blank=True)
    visitor_id = models.CharField(max_length=50, null=True, blank=True)
    customer_id = models.CharField(max_length=50, null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True)
    visit_timestamp = models.IntegerField(null=True, blank=True)
    operating_system = models.CharField(max_length=150, null=True, blank=True)
    device_category = models.CharField(max_length=150, null=True, blank=True)
    browser = models.CharField(max_length=150, null=True, blank=True)
    page_title = models.CharField(max_length=150, null=True, blank=True)
    page_location = models.CharField(max_length=150, null=True, blank=True)
    traffic_source = models.CharField(max_length=150, null=True, blank=True)
    event_name = models.CharField(max_length=150, null=True, blank=True)
    geolocation_city = models.CharField(max_length=50, null=True, blank=True)
    geolocation_state = models.CharField(max_length=50, null=True, blank=True)
    geolocation_country = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)
    

#Intraction by Google Analytics:
class Interaction_ga(models.Model):
    id = models.AutoField(primary_key=True)
    date = models.DateField(null=True, blank=True)
    event_name = models.CharField(max_length=50, null=True, blank=True)
    page_location = models.CharField(max_length=500, null=True, blank=True)
    operating_system = models.CharField(max_length=150, null=True, blank=True)
    device_category = models.CharField(max_length=150, null=True, blank=True)
    country = models.CharField(max_length=150, null=True, blank=True)
    browser = models.CharField(max_length=150, null=True, blank=True)
    event_count = models.IntegerField(null=True, blank=True)
    session_count = models.IntegerField(null=True, blank=True)
    import_id = models.CharField(max_length=30, null=True, blank=True)
    
  
#WebActivityType   
class WebActivityType(models.Model):
    name = models.CharField(max_length=60, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    value = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    
    
    
# WebActivity

# class WebActivity(models.Model):
#     page_id = models.CharField(max_length=50, null=True, blank=True)
#     session = models.CharField(max_length=50, null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True, null=True)
#     browser = models.CharField(max_length=80, null=True)
#     visitor = models.CharField(max_length=20)
#     activity_type = models.ForeignKey(
#         WebActivityType, on_delete=models.CASCADE)


# InteractionLocation

# class InteractionLocation(models.Model):
#     id = models.AutoField(primary_key=True)
#     interaction_id = models.CharField(max_length=50, null=True, blank=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# WebPage

# class WebPage(models.Model):
#     id = models.AutoField(primary_key=True)
#     page_id = models.CharField(max_length=50, null=True, blank=True)
#     url = models.CharField(max_length=200)
#     page_path = models.CharField(max_length=200)
#     page_title = models.CharField(max_length=150, null=True, blank=True)
#     search_keyword = models.CharField(max_length=150, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# Contact

# class Contact(models.Model):
#     id = models.AutoField(primary_key=True)
#     contact_id = models.CharField(max_length=50, null=True, blank=True)
#     contact_name = models.CharField(max_length=50, null=True, blank=True)
#     email = models.CharField(max_length=50, null=True, blank=True)
#     phone1 = models.CharField(max_length=50, null=True, blank=True)
#     phone2 = models.CharField(max_length=50, null=True, blank=True)
#     url = models.CharField(max_length=50, null=True, blank=True)
#     business_hour = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# EntityContactPoint

# class EntityContactPoint(models.Model):
#     id = models.AutoField(primary_key=True)
#     entity_id = models.CharField(max_length=50, null=True, blank=True)
#     contact_id = models.CharField(max_length=50, null=True, blank=True)
#     contact_role = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# EventProduct

# class EventProduct(models.Model):
#     id = models.AutoField(primary_key=True)
#     event_id = models.CharField(max_length=50, null=True, blank=True)
#     product_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# Event Preference

# class EventPreference(models.Model):
#     id = models.AutoField(primary_key=True)
#     preference_id = models.CharField(max_length=50, null=True, blank=True)
#     preference_type = models.CharField(max_length=50, null=True, blank=True)
#     preference_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
#     event_id = models.CharField(max_length=50, null=True, blank=True)
#     activity_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# Product Preferene

# class ProductPreference(models.Model):
#     id = models.AutoField(primary_key=True)
#     preference_id = models.CharField(max_length=50, null=True, blank=True)
#     preference_type = models.CharField(max_length=50, null=True, blank=True)
#     preference_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
#     product_id = models.CharField(max_length=50, null=True, blank=True)
#     activity_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)
    
# Item Preferene

# class ItemPreference(models.Model):
#     id = models.AutoField(primary_key=True)
#     preference_id = models.CharField(max_length=50, null=True, blank=True)
#     preference_type = models.CharField(max_length=50, null=True, blank=True)
#     preference_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
#     item_id = models.CharField(max_length=50, null=True, blank=True)
#     item_type = models.CharField(max_length=50, null=True, blank=True)
#     interaction_id = models.CharField(max_length=50, null=True, blank=True)
#     interaction_event_name = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# Session
# class Session(models.Model):
#     id = models.AutoField(primary_key=True)
#     visit_id = models.CharField(max_length=50, null=True, blank=True)
#     visit_date = models.DateField(null=True, blank=True)
#     visit_start_time = models.DateTimeField(null=True, blank=True)
#     visit_end_time = models.DateTimeField(null=True, blank=True)
#     visit_number = models.CharField(max_length=50, null=True, blank=True)
#     visit_duration = models.IntegerField(null=True)
#     operating_system = models.CharField(max_length=150, null=True, blank=True)
#     device_category = models.CharField(max_length=150, null=True, blank=True)
#     device_brand = models.CharField(max_length=150, null=True, blank=True)
#     browser = models.CharField(max_length=150, null=True, blank=True)
#     page_title = models.CharField(max_length=150, null=True, blank=True)
#     page_location = models.CharField(max_length=150, null=True, blank=True)
#     event_name = models.CharField(max_length=150, null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True, null=True)
#     customer_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)
    
# class SessionLocation(models.Model):
#     id = models.AutoField(primary_key=True)
#     session_id = models.CharField(max_length=50, null=True, blank=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# Customer
# class Customer(models.Model):
#     id = models.AutoField(primary_key=True)
#     customer_id = models.CharField(max_length=50, null=True, blank=True)
#     ip_address = models.CharField(max_length=50, null=True, blank=True)
#     contact_id = models.CharField(max_length=50, null=True, blank=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     dob = models.DateTimeField(null=True, blank=True)
#     name = models.CharField(max_length=50, null=True, blank=True)
#     gender = models.CharField(max_length=10, choices=(
#         ('male', 'male'), ('female', 'female')), default='event')
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# Journey
# class Journey(models.Model):
#     id = models.AutoField(primary_key=True)
#     journey_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)



# ProductResource

# class ProductResource(models.Model):
#     id = models.AutoField(primary_key=True)
#     product_id = models.CharField(max_length=50, null=True, blank=True)
#     resource_id = models.CharField(max_length=50, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# EventResource

# class EventResource(models.Model):
#     id = models.AutoField(primary_key=True)
#     event_id = models.CharField(max_length=50, null=True, blank=True)
#     resource_id = models.CharField(max_length=50, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# EntityResource

# class EntityResource(models.Model):
#     id = models.AutoField(primary_key=True)
#     entity_id = models.CharField(max_length=50, null=True, blank=True)
#     resource_id = models.CharField(max_length=50, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# EntityLocation

# class EntityLocation(models.Model):
#     id = models.AutoField(primary_key=True)
#     entity_id = models.CharField(max_length=50, null=True, blank=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# EventLocation

# class EventLocation(models.Model):
#     id = models.AutoField(primary_key=True)
#     event_id = models.CharField(max_length=50, null=True, blank=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     room = models.CharField(max_length=50, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)


# Location

# class GeoLocation(models.Model):
#     id = models.AutoField(primary_key=True)
#     location_id = models.CharField(max_length=50, null=True, blank=True)
#     location_name = models.CharField(max_length=50, null=True, blank=True)
#     address = models.CharField(max_length=150, null=True, blank=True)
#     address2 = models.CharField(max_length=150, null=True, blank=True)
#     longitude = models.CharField(max_length=50, null=True, blank=True)
#     latitude = models.CharField(max_length=50, null=True, blank=True)
#     city = models.CharField(max_length=50, null=True, blank=True)
#     state = models.CharField(max_length=50, null=True, blank=True)
#     region = models.CharField(max_length=50, null=True, blank=True)
#     zip = models.CharField(max_length=50, null=True, blank=True)
#     country = models.CharField(max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# Resource

# class Resource(models.Model):
#     id = models.AutoField(primary_key=True)
#     resource_id = models.CharField(max_length=50, null=True, blank=True)
#     resource_name = models.CharField(max_length=150, null=True, blank=True)
#     resource_type = models.CharField(max_length=50, null=True, blank=True)
#     resource_url = models.CharField(max_length=200, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)

# PriceType

# class PriceType(models.Model):
#     id = models.AutoField(primary_key=True)
#     price_type_id = models.CharField(max_length=50, null=True, blank=True)
#     price_type_name = models.CharField(max_length=50, null=True, blank=True)
#     price_type_currency = models.CharField(
#         max_length=50, null=True, blank=True)
#     import_id = models.CharField(max_length=30, null=True, blank=True)