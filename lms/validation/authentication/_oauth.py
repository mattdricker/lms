import secrets

import marshmallow
from webargs import fields

from lms.models import LTIUser
from lms.validation._base import PyramidRequestSchema, RequestsResponseSchema
from lms.validation.authentication._exceptions import (
    ExpiredJWTError,
    ExpiredStateParamError,
    InvalidJWTError,
    InvalidStateParamError,
    MissingStateParamError,
)
from lms.validation.authentication._helpers import _jwt


class OAuthCallbackSchema(PyramidRequestSchema):
    """
    Schema for validating OAuth 2 redirect_uri requests.

    This schema provides two convenience methods:

    First, :meth:`OAuthCallbackSchema.state_param` returns a string
    suitable for passing to an authorization server's authorization endpoint as
    the ``state`` query parameter::

       >>> schema = OAuthCallbackSchema()
       >>> schema.context['request'] = request
       >>> schema.state_param(request.lti_user)
       'xyz...123'

    Calling :meth:`OAuthCallbackSchema.state_param` also has the side
    effect of inserting a CSRF token into the session that will be checked
    against the ``state`` parameter when the authorization server returns the
    ``state`` parameter to us in a later ``redirect_uri`` request.

    Second, :meth:`OAuthCallbackSchema.lti_user` returns the
    models.LTIUser authenticated by the ``state`` param in the
    current request. This will raise if the request doesn't contain a ``state``
    query parameter or if the ``state`` is expired or invalid::

       >>> schema.lti_user()
       LTIUser(user_id='...', oauth_consumer_key='...')

    Finally, :class:`OAuthCallbackSchema` can also be used as a schema to
    guard a ``redirect_uri`` view, for example::

        @view_config(..., schema=OAuthCallbackSchema)
        def redirect_uri_view(request):
            # The authorization code and state sent by the authorization server
            # are available in request.parsed_params.
            authorization_code = request.parsed_params["code"]
            state = request.parsed_params["state"]
            ...

    This will prevent the view from being called if the code or state is
    missing, if the state is invalid or expired, or if there isn't a matching
    CSRF token in the session, and it will remove the CSRF token from the
    session so that it can't be reused.
    """

    location = "querystring"
    code = fields.Str(required=True)
    state = fields.Str(required=True)

    def __init__(self, request):
        super().__init__(request)
        self.context["secret"] = request.registry.settings["oauth2_state_secret"]

    def state_param(self):
        """
        Generate and return the value for an OAuth 2 state param.

        :rtype: str
        """
        request = self.context["request"]
        secret = request.registry.settings["oauth2_state_secret"]

        csrf = secrets.token_hex()

        data = {"user": request.lti_user._asdict(), "csrf": csrf}

        jwt_str = _jwt.encode_jwt(data, secret)

        request.session["oauth2_csrf"] = csrf

        return jwt_str

    def lti_user(self):
        """
        Return the LTIUser authenticated by the request's state param.

        Return the models.LTIUser authenticated by the current
        request's ``state`` query parameter.

        :raise MissingStateParamError: if the request has no ``state`` query
            parameter
        :raise ExpiredStateParamError: if the request's ``state`` param has
            expired
        :raise InvalidStateParamError: if the request's ``state`` param is
            invalid
        :rtype: str
        """
        request = self.context["request"]

        try:
            state = request.params["state"]
        except KeyError as err:
            raise MissingStateParamError() from err

        return LTIUser(**self._decode_state(state)["user"])

    @marshmallow.validates("state")
    def validate_state(self, state):
        """Validate the current request's ``state`` param."""
        request = self.context["request"]

        payload = self._decode_state(state)

        if payload["csrf"] != request.session.pop("oauth2_csrf", None):
            raise marshmallow.ValidationError("Invalid CSRF token")

    def _decode_state(self, state):
        """Decode the given state JWT and return its payload or raise."""
        secret = self.context["request"].registry.settings["oauth2_state_secret"]

        try:
            return _jwt.decode_jwt(state, secret)
        except ExpiredJWTError as err:
            raise ExpiredStateParamError() from err
        except InvalidJWTError as err:
            raise InvalidStateParamError() from err


class OAuthTokenResponseSchema(RequestsResponseSchema):
    """Schema for token responses from OAuth 2 authentication servers."""

    access_token = fields.Str(required=True)
    refresh_token = fields.Str()
    expires_in = fields.Integer()

    @marshmallow.validates("expires_in")
    def validate_quantity(self, expires_in):  # pylint:disable=no-self-use
        if expires_in <= 0:
            raise marshmallow.ValidationError("expires_in must be greater than 0")
