from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from pyramid.httpexceptions import HTTPInternalServerError

from lms.resources._js_config import JSConfig
from lms.services import CanvasAPIServerError
from lms.views.api.canvas import authorize
from lms.views.api.canvas.authorize import GROUPS_SCOPES

pytestmark = pytest.mark.usefixtures(
    "application_instance_service", "course_service", "canvas_api_client"
)


class TestAuthorize:
    def test_it_redirects_to_the_right_Canvas_endpoint(
        self, application_instance_service, pyramid_request
    ):
        response = authorize.authorize(pyramid_request)

        assert response.status_code == 302
        application_instance_service.get.assert_called_once_with()
        assert response.location.startswith(
            f"{application_instance_service.get.return_value.lms_url}login/oauth2/auth"
        )

    def test_it_includes_the_client_id_in_a_query_param(
        self, application_instance_service, pyramid_request
    ):
        response = authorize.authorize(pyramid_request)

        query_params = parse_qs(urlparse(response.location).query)

        application_instance_service.get.assert_called_once_with()
        assert query_params["client_id"] == [
            str(application_instance_service.get.return_value.developer_key)
        ]

    def test_it_includes_the_response_type_in_a_query_param(self, pyramid_request):
        response = authorize.authorize(pyramid_request)

        query_params = parse_qs(urlparse(response.location).query)

        assert query_params["response_type"] == ["code"]

    def test_it_includes_the_redirect_uri_in_a_query_param(self, pyramid_request):
        response = authorize.authorize(pyramid_request)

        query_params = parse_qs(urlparse(response.location).query)

        assert query_params["redirect_uri"] == [
            "http://example.com/canvas_oauth_callback"
        ]

    def test_it_includes_the_scopes_in_a_query_param(self, pyramid_request):
        self.assert_sections_scopes(authorize.authorize(pyramid_request))

    @pytest.mark.usefixtures("no_courses_with_sections_enabled")
    def test_sections_enabled_alone_triggers_sections_scopes(self, pyramid_request):
        self.assert_sections_scopes(authorize.authorize(pyramid_request))

    @pytest.mark.usefixtures("sections_disabled")
    def test_another_course_with_sections_alone_triggers_sections_scopes(
        self, pyramid_request
    ):
        self.assert_sections_scopes(authorize.authorize(pyramid_request))

    @pytest.mark.usefixtures("groups_enabled")
    def test_course_with_groups_enabled_triggers_groups_scopes(self, pyramid_request):
        self.assert_groups_scopes(authorize.authorize(pyramid_request))

    @pytest.mark.usefixtures("sections_not_supported")
    def test_no_sections_scopes_if_sections_is_disabled(self, pyramid_request):
        self.assert_file_scopes_only(authorize.authorize(pyramid_request))

    @pytest.mark.usefixtures("no_courses_with_sections_enabled")
    @pytest.mark.usefixtures("sections_disabled")
    def test_no_sections_scopes_if_no_courses_and_disabled(self, pyramid_request):
        self.assert_file_scopes_only(authorize.authorize(pyramid_request))

    def test_it_includes_the_state_in_a_query_param(
        self, pyramid_request, OAuthCallbackSchema, canvas_oauth_callback_schema
    ):
        response = authorize.authorize(pyramid_request)

        query_params = parse_qs(urlparse(response.location).query)

        OAuthCallbackSchema.assert_called_once_with(pyramid_request)
        canvas_oauth_callback_schema.state_param.assert_called_once_with()
        assert query_params["state"] == [
            canvas_oauth_callback_schema.state_param.return_value
        ]

    def assert_sections_scopes(self, response):
        query_params = parse_qs(urlparse(response.location).query)
        assert query_params["scope"] == [
            "url:GET|/api/v1/courses/:course_id/files "
            "url:GET|/api/v1/files/:id/public_url "
            "url:GET|/api/v1/courses/:id "
            "url:GET|/api/v1/courses/:course_id/sections "
            "url:GET|/api/v1/courses/:course_id/users/:id"
        ]

    def assert_groups_scopes(self, response):
        query_params = parse_qs(urlparse(response.location).query)

        assert set(GROUPS_SCOPES).issubset(set(query_params["scope"][0].split()))

    def assert_file_scopes_only(self, response):
        query_params = parse_qs(urlparse(response.location).query)
        assert query_params["scope"] == [
            "url:GET|/api/v1/courses/:course_id/files url:GET|/api/v1/files/:id/public_url"
        ]

    @pytest.fixture
    def sections_not_supported(self, application_instance_service):
        application_instance_service.get.return_value.developer_key = None

    @pytest.fixture
    def sections_disabled(self, application_instance_service):
        application_instance_service.get.return_value.settings.set(
            "canvas", "sections_enabled", False
        )

    @pytest.fixture
    def groups_enabled(self, application_instance_service):
        application_instance_service.get.return_value.settings.set(
            "canvas", "groups_enabled", True
        )

    @pytest.fixture
    def no_courses_with_sections_enabled(self, course_service):
        course_service.any_with_setting.return_value = False


class TestOAuth2Redirect:
    def test_it_gets_an_access_token_from_canvas(
        self, canvas_api_client, pyramid_request
    ):
        authorize.oauth2_redirect(pyramid_request)

        canvas_api_client.get_token.assert_called_once_with("test_authorization_code")

    def test_it_500s_if_get_token_raises(self, canvas_api_client, pyramid_request):
        canvas_api_client.get_token.side_effect = CanvasAPIServerError()

        with pytest.raises(HTTPInternalServerError):
            authorize.oauth2_redirect(pyramid_request)

    @pytest.fixture
    def pyramid_request(self, pyramid_request):
        pyramid_request.parsed_params = {"code": "test_authorization_code"}
        return pyramid_request


class TestOAuth2RedirectError:
    @pytest.mark.parametrize(
        "params,invalid_scope",
        [
            ({"error": "invalid_scope"}, True),
            ({"error": "unknown_error"}, False),
            ({"foo": "bar"}, False),
            ({"error_description": "Something went wrong"}, False),
        ],
    )
    def test_it_configures_frontend_app(self, pyramid_request, params, invalid_scope):
        pyramid_request.params.clear()
        pyramid_request.params.update(params)
        pyramid_request.lti_user = None

        scopes = (
            "url:GET|/api/v1/courses/:course_id/files",
            "url:GET|/api/v1/files/:id/public_url",
            "url:GET|/api/v1/courses/:id",
            "url:GET|/api/v1/courses/:course_id/sections",
            "url:GET|/api/v1/courses/:course_id/users/:id",
            "url:GET|/api/v1/courses/:course_id/group_categories",
            "url:GET|/api/v1/group_categories/:group_category_id/groups",
            "url:GET|/api/v1/courses/:course_id/groups",
        )

        authorize.oauth2_redirect_error(pyramid_request)

        js_config = pyramid_request.context.js_config
        js_config.enable_oauth2_redirect_error_mode.assert_called_with(
            auth_route="canvas_api.oauth.authorize",
            error_details=params.get("error_description"),
            is_scope_invalid=invalid_scope,
            canvas_scopes=scopes,
        )

    @pytest.fixture
    def pyramid_request(self, pyramid_request, OAuth2RedirectResource):
        context = OAuth2RedirectResource(pyramid_request)
        context.js_config = mock.create_autospec(JSConfig, spec_set=True, instance=True)
        pyramid_request.context = context
        return pyramid_request

    @pytest.fixture(autouse=True)
    def OAuth2RedirectResource(self, patch):
        return patch("lms.resources.OAuth2RedirectResource")


@pytest.fixture(autouse=True)
def OAuthCallbackSchema(patch):
    return patch("lms.views.api.canvas.authorize.OAuthCallbackSchema")


@pytest.fixture
def canvas_oauth_callback_schema(OAuthCallbackSchema):
    schema = OAuthCallbackSchema.return_value
    schema.state_param.return_value = "test_state"
    return schema
