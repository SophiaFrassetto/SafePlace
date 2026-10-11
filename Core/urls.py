
from django.urls import include, path

from SafeSpace.views import auth

urlpatterns = [
    path('', auth.home, name='home'),
    path('diario/', auth.diary, name='diary'),
    path(
        'diario/afazeres/<uuid:task_id>/concluir/',
        auth.complete_diary_task,
        name='diary_task_complete',
    ),
    path('saude/', auth.health, name='health'),
    path('sos/', auth.sos, name='sos'),
    path('sos/cartao/<str:token>/', auth.sos_card, name='sos_card'),
    path('sos/cartao/<str:token>/qr.png', auth.sos_qr, name='sos_qr'),
    path(
        'sos/cartao/<str:token>/baixar.svg',
        auth.sos_card_download,
        name='sos_card_download',
    ),
    path('perfil/', auth.profile, name='profile'),
    path('perfil/foto/', auth.profile_picture, name='profile_picture'),
    path('logout/', auth.logout_view, name='logout'),
    path('login/', include('SafeSpace.urls')),
]
