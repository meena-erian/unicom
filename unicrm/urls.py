from django.urls import path

from .views import TemplateVariableListView

app_name = 'unicrm'

urlpatterns = [
    path('api/template-variables/', TemplateVariableListView.as_view(), name='template_variables'),
]

