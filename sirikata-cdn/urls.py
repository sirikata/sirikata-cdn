from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^view/(?P<filename>[\w\-\./]+)$', 'content.views.view'),
    (r'^edit/(?P<filename>[\w\-\./]+)$', 'content.views.edit_file'),
    (r'^clone/(?P<filename>[\w\-\./]+)$', 'content.views.clone_file'),
    (r'^delete/(?P<filename>[\w\-\./]+)$', 'content.views.delete_file'),
    (r'^dns/(?P<filename>[\w\-\./]+)$', 'content.views.dns'),
    (r'^download/(?P<hash>[a-z0-9]{64})$', 'content.views.download'),
    (r'^download/(?P<hash>[a-z0-9]{64})/(?P<filename>[\w\-\./]+)$', 'content.views.download'),
    (r'^download/(?P<filename>[\w\-\./]+)$', 'content.views.download_path'),
    (r'^upload/$', 'content.views.upload'),
    (r'^upload/(?P<task_id>[\w\-]+)$', 'content.views.upload'),
    (r'^upload/choice/(?P<task_id>[\w\-]+)$', 'content.views.upload_choice'),
    (r'^upload/processing/(?P<task_id>[\w\-]+)$', 'content.views.upload_processing'),
    (r'^upload/processing/(?P<action>.*)/(?P<task_id>[\w\-]+)$', 'content.views.upload_processing'),
    (r'^upload/import/(?P<task_id>[\w\-]+)$', 'content.views.upload_import'),
    (r'^uploads/$', 'users.views.uploads'),
    (r'^login/openid_select$', 'users.views.openid_select'),
    (r'^login/openid_return$', 'users.views.openid_return'),
    (r'^login/openid_link$', 'users.views.openid_link'),
    (r'^login/$', 'users.views.login'),
    (r'^logout/$', 'users.views.logout'),
    (r'^api/modelinfo/(?P<filename>[\w\-\./]+)$', 'content.views.view_json'),
    (r'^api/keepalive/(?P<filename>[\w\-\./]+)$', 'content.views.ephemeral_keepalive'),
    (r'^api/browse/(?P<start>[0-9]*)$', 'content.views.browse_json'),
    (r'^$', 'content.views.browse'),
    (r'^profile/(?P<username>\w+)$', 'users.views.profile'),
    (r'^user/oauth/generate_access_token$', 'users.views.generate_access_token'),
    (r'^user/oauth/remove_access_token$', 'users.views.remove_access_token'),
    (r'^user/oauth/generate_consumer_token$', 'users.views.generate_consumer_token'),
    (r'^user/oauth/remove_consumer_token$', 'users.views.remove_consumer_token'),
    (r'^api/search$', 'content.views.search_json'),
    (r'^about/$', 'misc.views.about'),
    (r'^search$', 'content.views.search'),
    (r'^compare/progressive$', 'content.views.compare_progressive'),
    (r'^api/upload$', 'content.views.api_upload'),
    (r'^admin/update-labels(?P<filename>[\w\-\./]+)$', 'content.views.update_labels'),
)

if settings.DEBUG:
    urlpatterns += patterns('django.views.static',
        (r'^media/(?P<path>.*)$', 'serve',
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    )
