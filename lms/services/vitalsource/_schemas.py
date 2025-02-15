"""
Schemas for VitalSource API responses.

See: https://developer.vitalsource.com/hc/en-us/categories/360001974433
"""
from marshmallow import EXCLUDE, Schema, fields

from lms.validation._base import RequestsResponseSchema


class BookInfoSchema(RequestsResponseSchema):
    class ResourceLinks(Schema):
        class Meta:
            unknown = EXCLUDE

        cover_image = fields.Str(required=True)

    vbid = fields.Str(required=True)
    title = fields.Str(required=True)

    resource_links = fields.Nested(ResourceLinks, required=True)


class BookTOCSchema(RequestsResponseSchema):
    class Chapter(Schema):
        class Meta:
            unknown = EXCLUDE

        title = fields.Str(required=True)
        cfi = fields.Str(required=True)
        page = fields.Str(required=True)

    table_of_contents = fields.List(fields.Nested(Chapter), required=True)
