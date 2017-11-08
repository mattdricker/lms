
from __future__ import unicode_literals

from pyramid.view import view_config


@view_config(route_name='config_xml',
             renderer='config.xml.jinja2',
             request_method='GET')
def config_xml(request):
    request.response.content_type = 'text/xml'

    return {
      'launch_url': request.route_url('lti_launches'),
      'resource_selection_url': request.route_url('content_item_selection'),
    }
