"""Proxy API views for files-related Canvas API endpoints."""
from pyramid.view import view_config, view_defaults

from lms.security import Permissions
from lms.services.canvas import CanvasService
from lms.views import helpers


@view_defaults(permission=Permissions.API, renderer="json")
class FilesAPIViews:
    def __init__(self, request):
        self.request = request
        self.canvas = request.find_service(CanvasService)

    @view_config(request_method="GET", route_name="canvas_api.courses.files.list")
    def list_files(self):
        """
        Return the list of files in the given course.

        :raise lms.services.CanvasAPIError: if the Canvas API request fails.
            This exception is caught and handled by an exception view.
        """
        return self.canvas.api.list_files(self.request.matchdict["course_id"])

    @view_config(request_method="GET", route_name="canvas_api.files.via_url")
    def via_url(self):
        """
        Return the Via URL for annotating the given Canvas file.

        :raise lms.services.CanvasAPIError: if the Canvas API request fails.
            This exception is caught and handled by an exception view.
        """
        application_instance = self.request.find_service(
            name="application_instance"
        ).get()

        assignment = self.request.find_service(name="assignment").get(
            application_instance.tool_consumer_instance_guid,
            self.request.matchdict["resource_link_id"],
        )

        public_url = self.canvas.public_url_for_file(
            assignment,
            self.request.matchdict["file_id"],
            self.request.matchdict["course_id"],
            check_in_course=self.request.lti_user.is_instructor,
        )

        # Currently we only let users pick PDF files, so we can save a little
        # time by specifying this, instead of Via having to work it out
        via_url = helpers.via_url(self.request, public_url, content_type="pdf")

        return {"via_url": via_url}
