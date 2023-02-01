from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('result/', views.result, name='result'),
    path('table/', views.person_list, name='result'),
    path('upload/', views.handle_upload, name='handle_upload'),
    path('dados/', views.dadosGrafico, name='dadosGrafico')

    # path('processed/', views.processed, name='processed'),
    # path('', views.index, name='index'),
    # path('login', views.user_login, name='login'),
    # Demo view
	# path('demo/', views.demo_view, name='demo'),

]
