import functools

from lms.models import GroupInfo, HUser
from lms.resources._js_config.file_picker_config import FilePickerConfig
from lms.services import HAPIError
from lms.validation.authentication import BearerTokenSchema
from lms.views.helpers import via_url


class JSConfig:
    """The config for the app's JavaScript code."""

    def __init__(self, context, request):
        self._context = context
        self._request = request
        self._authority = request.registry.settings["h_authority"]
        self._grading_info_service = request.find_service(name="grading_info")
        self._lti_user = request.lti_user

    @property
    def _h_user(self):
        return self._lti_user.h_user

    @property
    def _consumer_key(self):
        return self._lti_user.oauth_consumer_key

    def _application_instance(self):
        """
        Return the current request's ApplicationInstance.

        :raise ConsumerKeyError: if request.lti_user.oauth_consumer_key isn't in the DB
        """
        return self._request.find_service(name="application_instance").get()

    def add_canvas_file_id(self, course_id, resource_link_id, canvas_file_id):
        """
        Set the document to the Canvas file with the given canvas_file_id.

        This configures the frontend to make an API call to get the URL to use
        as the src for the Via iframe.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing
        """
        self._config["api"]["viaUrl"] = {
            "authUrl": self._request.route_url("canvas_api.oauth.authorize"),
            "path": self._request.route_path(
                "canvas_api.files.via_url",
                course_id=course_id,
                resource_link_id=resource_link_id,
                file_id=canvas_file_id,
            ),
        }
        self._add_canvas_speedgrader_settings(canvas_file_id=canvas_file_id)

    def add_document_url(self, document_url):
        """
        Set the document to the document at the given document_url.

        This configures the frontend to inject the Via iframe with this URL as
        its src immediately, without making any further API requests to get the
        Via URL.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing
        """
        if document_url.startswith("blackboard://"):
            self._config["api"]["viaUrl"] = {
                "authUrl": self._request.route_url("blackboard_api.oauth.authorize"),
                "path": self._request.route_path(
                    "blackboard_api.files.via_url",
                    course_id=self._request.params["context_id"],
                    _query={"document_url": document_url},
                ),
            }
        else:
            self._config["viaUrl"] = via_url(self._request, document_url)
            self._add_canvas_speedgrader_settings(document_url=document_url)

    def add_vitalsource_launch_config(self, book_id, cfi=None):
        vitalsource_svc = self._request.find_service(name="vitalsource")
        launch_url, launch_params = vitalsource_svc.get_launch_params(
            book_id, cfi, self._request.lti_user
        )
        self._config["vitalSource"] = {
            "launchUrl": launch_url,
            "launchParams": launch_params,
        }
        self._add_canvas_speedgrader_settings(
            vitalsource_book_id=book_id, vitalsource_cfi=cfi
        )

    def asdict(self):
        """
        Return the configuration for the app's JavaScript code.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing

        :rtype: dict
        """
        return self._config

    def enable_oauth2_redirect_error_mode(
        self,
        auth_route,
        error_details="",
        is_scope_invalid=False,
        canvas_scopes=None,
    ):
        """
        Configure the frontend to show the "Authorization failed" dialog.

        This is shown when authorizing with a third-party OAuth API like the
        Canvas API or the Blackboard API fails after the redirect to the
        third-party authorization endpoint.

        :param error_details: Technical details of the error
        :type error_details: str
        :param auth_route: route for the "Try again" button in the dialog
        :type auth_route: str
        :param is_scope_invalid: `True` if authorization failed because the
          OAuth client does not have access to all the necessary scopes
        :type is_scope_invalid: bool
        :param canvas_scopes: List of scopes that were requested
        :type canvas_scopes: list(str)
        """
        if self._lti_user:
            bearer_token = BearerTokenSchema(self._request).authorization_param(
                self._lti_user
            )
            auth_url = self._request.route_url(
                auth_route,
                _query=[("authorization", bearer_token)],
            )
        else:
            auth_url = None

        self._config.update(
            {
                "mode": "oauth2-redirect-error",
                "OAuth2RedirectError": {
                    "authUrl": auth_url,
                    "invalidScope": is_scope_invalid,
                    "errorDetails": error_details,
                    "canvasScopes": canvas_scopes or [],
                },
            }
        )

    def enable_lti_launch_mode(self):
        """
        Put the JavaScript code into "LTI launch" mode.

        This mode launches an assignment.

        :raise ConsumerKeyError: if request.lti_user.oauth_consumer_key isn't in the DB
        """
        self._config["mode"] = "basic-lti-launch"

        self._config["api"]["sync"] = self._sync_api()

        # The config object for the Hypothesis client.
        # Our JSON-RPC server passes this to the Hypothesis client over
        # postMessage.
        self._config["hypothesisClient"] = self._hypothesis_client

        self._config["rpcServer"] = {
            "allowedOrigins": self._request.registry.settings["rpc_allowed_origins"]
        }

    def enable_content_item_selection_mode(self, form_action, form_fields):
        """
        Put the JavaScript code into "content item selection" mode.

        This mode shows teachers an assignment configuration UI where they can
        choose the document to be annotated for the assignment.

        :param form_action: the HTML `action` attribute for the URL that we'll
            submit the user's chosen document to
        :param form_fields: the fields (keys and values) to include in the
            HTML form that we submit

        :raise ConsumerKeyError: if request.lti_user.oauth_consumer_key isn't in the DB
        """

        args = self._context, self._request, self._application_instance()

        self._config.update(
            {
                "mode": "content-item-selection",
                "filePicker": {
                    "formAction": form_action,
                    "formFields": form_fields,
                    # Specific config for pickers
                    "blackboard": FilePickerConfig.blackboard_config(*args),
                    "canvas": FilePickerConfig.canvas_config(*args),
                    "google": FilePickerConfig.google_files_config(*args),
                    "microsoftOneDrive": FilePickerConfig.microsoft_onedrive(*args),
                    "vitalSource": FilePickerConfig.vital_source_config(*args),
                },
            }
        )

    def maybe_enable_grading(self):
        """Enable our LMS app's built-in assignment grading UI, if appropriate."""

        if not self._lti_user.is_instructor:
            # Only instructors can grade assignments.
            return

        if "lis_outcome_service_url" not in self._request.params:
            # Only "gradeable" assignments can be graded.
            # Assignments that don't have the lis_outcome_service_url param
            # aren't set as gradeable in the LMS.
            return

        if self._context.is_canvas:
            # Don't show our built-in grader in Canvas because it has its own
            # "SpeedGrader" and we support that instead.
            return

        self._config["grading"] = {
            "enabled": True,
            "courseName": self._request.params.get("context_title"),
            "assignmentName": self._request.params.get("resource_link_title"),
            "students": list(self._get_students()),
        }

    def maybe_set_focused_user(self):
        """
        Configure the Hypothesis client to focus on a particular user.

        If there is a focused_user request param then add the necessary
        Hypothesis client config to get the client to focus on the particular
        user identified by the focused_user param, showing only that user's
        annotations and not others.

        In practice the focused_user param is only ever present in Canvas
        SpeedGrader launches. We add a focused_user query param to the
        SpeedGrader LTI launch URLs that we submit to Canvas for each student
        when the student launches an assignment. Later, Canvas uses these URLs
        to launch us when a teacher grades the assignment in SpeedGrader.

        In theory, though, the focused_user param could work outside of Canvas
        as well if we ever want it to.

        :raise ConsumerKeyError: if request.lti_user.oauth_consumer_key isn't in the DB
        """
        focused_user = self._request.params.get("focused_user")

        if not focused_user:
            return

        self._hypothesis_client["focus"] = {"user": {"username": focused_user}}

        # Unfortunately we need to pass the user's current display name to the
        # Hypothesis client, and we need to make a request to the h API to
        # retrieve that display name.
        try:
            display_name = (
                self._request.find_service(name="h_api")
                .get_user(focused_user)
                .display_name
            )
        except HAPIError:
            display_name = "(Couldn't fetch student name)"

        self._hypothesis_client["focus"]["user"]["displayName"] = display_name

    def _add_canvas_speedgrader_settings(self, **kwargs):
        """
        Add config used by the JS to call our record_canvas_speedgrader_submission API.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing
        """
        lis_result_sourcedid = self._request.params.get("lis_result_sourcedid")
        lis_outcome_service_url = self._request.params.get("lis_outcome_service_url")

        # Don't set the Canvas submission params in non-Canvas LMS's.
        if not self._context.is_canvas:
            return

        # When a Canvas assignment is launched by a teacher or other
        # non-gradeable user there's no lis_result_sourcedid in the LTI
        # launch params.
        # Don't post submission to Canvas for these cases.
        if not lis_result_sourcedid:
            return

        # When a Canvas assignment isn't gradeable there's no
        # lis_outcome_service_url.
        # Don't post submission to Canvas for these cases.
        if not lis_outcome_service_url:
            return

        self._config["canvas"]["speedGrader"] = {
            "submissionParams": {
                "h_username": self._h_user.username,
                "lis_result_sourcedid": lis_result_sourcedid,
                "lis_outcome_service_url": lis_outcome_service_url,
                "learner_canvas_user_id": self._request.params["custom_canvas_user_id"],
                "group_set": self._request.params.get("group_set"),
                **kwargs,
            },
        }

    def _auth_token(self):
        """Return the authToken setting."""
        return BearerTokenSchema(self._request).authorization_param(self._lti_user)

    @property
    @functools.lru_cache()
    def _config(self):
        """
        Return the current configuration dict.

        This method populates the default parameters used by all frontend
        apps. The `enable_xxx_mode` methods configures the specific parameters
        needed by a particular frontend mode.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing

        :rtype: dict
        """
        # This is a lazy-computed property so that if it's going to raise an
        # exception that doesn't happen until someone actually reads it.
        # If it instead crashed in JSConfig.__init__() that would happen
        # earlier in the request processing pipeline and could change the error
        # response.
        #
        # We cache this property (@functools.lru_cache()) so that it's
        # mutable. You can do self._config["foo"] = "bar" and the mutation will
        # be preserved.

        config = {
            # Settings to do with the API that the backend provides for the
            # frontend to call.
            "api": {
                # The auth token that the JavaScript code will use to
                # authenticate itself to the API.
                "authToken": self._auth_token()
            },
            "canvas": {},
            # Some debug information, currently used in the Gherkin tests.
            "debug": {"tags": []},
            # Tell the JavaScript code whether we're in "dev" mode.
            "dev": self._request.registry.settings["dev"],
            # What "mode" to put the JavaScript code in.
            # For example in "basic-lti-launch" mode the JavaScript code
            # launches its BasicLtiLaunchApp, whereas in
            # "content-item-selection" mode it launches its FilePickerApp.
            "mode": None,
        }

        if self._lti_user:
            config["debug"]["tags"].append(
                "role:instructor" if self._lti_user.is_instructor else "role:learner"
            )

        return config

    def _get_students(self):
        """
        Yield the student dicts for the request.

        Yield one student dict for each student who has launched the assignment
        and had grading info recorded for them.
        """
        grading_infos = self._grading_info_service.get_by_assignment(
            oauth_consumer_key=self._consumer_key,
            context_id=self._request.params.get("context_id"),
            resource_link_id=self._request.params.get("resource_link_id"),
        )

        # Yield a "student" dict for each GradingInfo.
        for grading_info in grading_infos:
            h_user = HUser(
                username=grading_info.h_username,
                display_name=grading_info.h_display_name,
            )
            yield {
                "userid": h_user.userid(self._authority),
                "displayName": h_user.display_name,
                "LISResultSourcedId": grading_info.lis_result_sourcedid,
                "LISOutcomeServiceUrl": grading_info.lis_outcome_service_url,
            }

    @property
    @functools.lru_cache()
    def _hypothesis_client(self):
        """
        Return the config object for the Hypothesis client.

        :raise HTTPBadRequest: if a request param needed to generate the config
            is missing

        :raise ConsumerKeyError: if request.lti_user.oauth_consumer_key isn't in the DB
        """
        # This is a lazy-computed property so that if it's going to raise an
        # exception that doesn't happen until someone actually reads it.
        # If it instead crashed in JSConfig.__init__() that would happen
        # earlier in the request processing pipeline and could change the error
        # response.
        #
        # We cache this property (@functools.lru_cache()) so that it's
        # mutable. You can do self._hypothesis_client["foo"] = "bar" and the
        # mutation will be preserved.

        if not self._application_instance().provisioning:
            return {}

        api_url = self._request.registry.settings["h_api_url_public"]

        # Generate a short-lived login token for the Hypothesis client.
        grant_token_svc = self._request.find_service(name="grant_token")
        grant_token = grant_token_svc.generate_token(self._h_user)

        return {
            # For documentation of these Hypothesis client settings see:
            # https://h.readthedocs.io/projects/client/en/latest/publishers/config/#configuring-the-client-using-json
            "services": [
                {
                    "allowFlagging": False,
                    "allowLeavingGroups": False,
                    "apiUrl": api_url,
                    "authority": self._authority,
                    "enableShareLinks": False,
                    "grantToken": grant_token,
                    "groups": self._groups(),
                }
            ]
        }

    def _groups(self):
        if (
            self._context.canvas_sections_enabled
            or self._context.canvas_is_group_launch
        ):
            return "$rpc:requestGroups"
        return [self._context.h_group.groupid(self._authority)]

    def _sync_api(self):
        if (
            not self._context.canvas_sections_enabled
            and not self._context.canvas_is_group_launch
        ):
            return None

        req = self._request

        sync_api_config = {
            "authUrl": req.route_url("canvas_api.oauth.authorize"),
            "path": req.route_path("canvas_api.sync"),
            "data": {
                "lms": {
                    "tool_consumer_instance_guid": req.params[
                        "tool_consumer_instance_guid"
                    ],
                },
                "course": {
                    "context_id": req.params["context_id"],
                    "custom_canvas_course_id": req.params["custom_canvas_course_id"],
                    "group_set": req.params.get("group_set"),
                },
                "group_info": {
                    key: value
                    for key, value in req.params.items()
                    if key in GroupInfo.columns()
                },
            },
        }

        if "learner_canvas_user_id" in req.params:
            sync_api_config["data"]["learner"] = {
                "canvas_user_id": req.params["learner_canvas_user_id"],
                "group_set": req.params.get("group_set"),
            }

        return sync_api_config
