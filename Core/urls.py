
from django.urls import include, path

from SafeSpace.views import auth, diary, home, profile, sos

urlpatterns = [
    path('', home.home, name='home'),
    path('diario/', diary.diary, name='diary'),
    path(
        'diario/afazeres/<uuid:task_id>/concluir/',
        diary.complete_diary_task,
        name='diary_task_complete',
    ),
    path('saude/', home.health, name='health'),
    path('sos/', sos.sos, name='sos'),
    path('sos/cartao/<str:token>/', sos.sos_card, name='sos_card'),
    path('sos/cartao/<str:token>/qr.png', sos.sos_qr, name='sos_qr'),
    path(
        'sos/cartao/<str:token>/baixar.svg',
        sos.sos_card_download,
        name='sos_card_download',
    ),
    path('perfil/', profile.profile, name='profile'),
    path('perfil/foto/', profile.profile_picture, name='profile_picture'),
    path('logout/', auth.logout_view, name='logout'),
    path('login/', include('SafeSpace.urls')),
]
