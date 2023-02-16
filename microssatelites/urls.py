from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('result/', views.result, name='result'),
    # path('upload/', views.handle_upload, name='handle_upload'),
    path('dados/', views.dadosGrafico, name='dadosGrafico'),
    path('processament/', views.processament, name='processament'),
    path('get_processing_status/', views.get_processing_status, name='get_processing_status'),
    path('get_uploaded_file/', views.get_uploaded_file, name='get_uploaded_file'),
    path('download/', views.download_folder, name='download_folder'),
    # path('processed/', views.processed, name='processed'),
    # path('', views.index, name='index'),
    # path('login', views.user_login, name='login'),
    # Demo view
	# path('demo/', views.demo_view, name='demo'),

]
