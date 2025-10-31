from django.urls import path

from .views import TemplateVariableListView
from .views_communication import CommunicationListView, CommunicationDetailView

app_name = 'unicrm'

urlpatterns = [
    path('api/template-variables/', TemplateVariableListView.as_view(), name='template_variables'),
    path('communications/', CommunicationListView.as_view(), name='communications-list'),
    path('communications/<int:pk>/', CommunicationDetailView.as_view(), name='communications-detail'),
]
