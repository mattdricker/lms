from unittest import mock

import marshmallow
import pytest

from lms.validation._helpers import instantiate_schema


class TestInstantiateSchema:
    def test_it_returns_dict_schemas_unmodified(self, pyramid_request):
        schema = {
            "field1": marshmallow.fields.Str(),
            "field2": marshmallow.fields.Str(required=True),
        }

        assert instantiate_schema(schema, pyramid_request) == schema

    def test_it_returns_class_schemas_instantiated(self, pyramid_request):
        instantiated_schema = instantiate_schema(MySchema, pyramid_request)

        assert isinstance(instantiated_schema, MySchema)

    def test_it_adds_the_request_to_a_schema_objects_context(self, pyramid_request):
        instantiated_schema = instantiate_schema(MySchema, pyramid_request)

        assert instantiated_schema.context["request"] == pyramid_request


class MySchema(marshmallow.Schema):
    field1 = marshmallow.fields.Str()
    field2 = marshmallow.fields.Str(required=True)

    class Meta:
        strict = True
