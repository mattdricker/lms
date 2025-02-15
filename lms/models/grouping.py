import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from lms.db import BASE
from lms.models import CreatedUpdatedMixin
from lms.models.application_settings import ApplicationSettings

MAX_GROUP_NAME_LENGTH = 25


class Grouping(CreatedUpdatedMixin, BASE):
    __tablename__ = "grouping"
    __mapper_args__ = {"polymorphic_identity": "grouping", "polymorphic_on": "type"}
    __table_args__ = (
        sa.UniqueConstraint("application_instance_id", "authority_provided_id"),
        sa.UniqueConstraint("lms_id", "application_instance_id", "parent_id", "type"),
    )

    id = sa.Column(sa.Integer(), autoincrement=True, primary_key=True)

    application_instance_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("application_instances.id", ondelete="cascade"),
        nullable=False,
    )
    application_instance = sa.orm.relationship("ApplicationInstance")

    #: The authority_provided_id of the Group that was created for this Grouping in h's DB.
    authority_provided_id = sa.Column(sa.UnicodeText(), nullable=False)

    #: The id of the parent grouping that this grouping belongs to.
    #:
    #: For example if the grouping represents a Canvas section or group then parent_id
    #: will reference the grouping for the course that the section or group belongs to.
    parent_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey("grouping.id", ondelete="cascade"),
        nullable=True,
    )
    children = sa.orm.relationship(
        "Grouping", backref=sa.orm.backref("parent", remote_side=[id])
    )

    #: The LMS's ID for the grouping.
    #:
    #: For example for a course this is the value of the context_id launch param.
    #: For a Canvas section or group this is the value of the section or group's id
    #: from the Canvas API.
    #:
    #: lms_id may not be unique without `parent_id`. For example a Canvas instance may
    #: have multiple sections or groups with the same id in different courses. In this
    #: case multiple Grouping's would have the same lms_id but they will have different
    #: parent_id's.
    lms_id = sa.Column(sa.Unicode(), nullable=False)

    #: Full name given on the LMS (e.g. "A course name 101")
    lms_name = sa.Column(sa.UnicodeText(), nullable=False)

    type = sa.Column(sa.Unicode(), nullable=False)

    settings = sa.Column(
        "settings",
        ApplicationSettings.as_mutable(JSONB),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    extra = sa.Column(
        "extra",
        MutableDict.as_mutable(JSONB),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )

    @property
    def name(self):
        """Return an h-compatible group name."""
        name = self.lms_name.strip()

        if len(name) > MAX_GROUP_NAME_LENGTH:
            return name[: MAX_GROUP_NAME_LENGTH - 1].rstrip() + "…"

        return name

    def groupid(self, authority):
        return f"group:{self.authority_provided_id}@{authority}"


class CanvasSection(Grouping):
    __mapper_args__ = {"polymorphic_identity": "canvas_section"}


class CanvasGroup(Grouping):
    __mapper_args__ = {"polymorphic_identity": "canvas_group"}


class Course(Grouping):
    __mapper_args__ = {"polymorphic_identity": "course"}
