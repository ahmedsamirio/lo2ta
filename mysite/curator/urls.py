from django.urls import path
from . import views

app_name = 'curator'

urlpatterns = [
    path('', views.home, name='home'),
    path('price', views.findbyprice, name='price'),
    path('results', views.price_results, name='results'),
    path('model', views.model, name='model'),
]