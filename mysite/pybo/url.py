from django.urls import path

from . import views

urlpatterns = [
    path('', views.index),
    path('set-folder/', views.set_folder, name='set_folder'),
    path('get-image/', views.get_image, name='get_image'),
    path('get-yolo-image/', views.get_yolo_image, name='get_yolo_image'),
    path('receive-image/', views.receive_image, name='receive_image'),
]