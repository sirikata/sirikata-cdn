from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^upload/$', 'content.views.upload'),
    (r'^upload/(?P<task_id>[\w\-]+)$', 'content.views.upload'),
    (r'^upload/choice/(?P<task_id>[\w\-]+)$', 'content.views.upload_choice'),
    (r'^upload/processing/(?P<task_id>[\w\-]+)$', 'content.views.upload_processing'),
    (r'^upload/processing/(?P<action>.*)/(?P<task_id>[\w\-]+)$', 'content.views.upload_processing'),
    (r'^uploads/$', 'users.views.uploads'),
    (r'^login/openid_select$', 'users.views.openid_select'),
    (r'^login/openid_return$', 'users.views.openid_return'),
    (r'^login/openid_link$', 'users.views.openid_link'),
    (r'^login/$', 'users.views.login'),
    (r'^logout/$', 'users.views.logout'),
    (r'^$', 'content.views.index'),
)

if settings.DEBUG:
    urlpatterns += patterns('django.views.static',
        (r'^media/(?P<path>.*)$', 'serve',
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    )
