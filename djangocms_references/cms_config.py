from collections import defaultdict

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _

from cms.app_base import CMSAppConfig, CMSAppExtension
from cms.plugin_base import CMSPlugin
from cms.plugin_pool import plugin_pool

from .datastructures import ExtraColumn
from .helpers import get_versionable_for_content


class ReferencesCMSExtension(CMSAppExtension):
    def __init__(self):
        self.reference_models = self._make_default()
        self.reference_plugins = self._make_default()
        self.extra_columns = []
        self.extra_column_modifiers = []

    def _make_default(self):
        return defaultdict(lambda: defaultdict(set))

    def register_fields(self, fields):
        # generate reference_models and reference_plugins dict object
        for field in fields:
            model = field.field.model
            related_model = field.field.related_model
            if (
                issubclass(model, (CMSPlugin,))
                and model.__name__ in plugin_pool.plugins
            ):
                store = self.reference_plugins
            else:
                store = self.reference_models
            store[related_model][model].add(field.field.name)

    def configure_extra_columns(self, attr_list):
        for attrs, modifier in attr_list:
            self.extra_column_modifiers.append(modifier)
            for attr in attrs:
                _attr = ExtraColumn(*attr)
                # FIXME error out if already in the list (?)
                self.extra_columns.append(_attr)

    def configure_app(self, cms_config):
        """
        Third party app can define set object as reference_fields (like Child.parent)
        to define child parent relation of any field to model.
        Based on definition register_fields method generate model and plugin dict
        """
        if getattr(cms_config, "reference_fields", None) is not None:
            reference_fields = getattr(cms_config, "reference_fields")
            if isinstance(reference_fields, set):
                self.register_fields(reference_fields)
            else:
                raise ImproperlyConfigured(
                    "Reference model configuration must be a set instance"
                )
        self.configure_extra_columns(
            getattr(cms_config, "reference_extra_columns", [])
        )


def version_queryset_modifier(queryset):
    if get_versionable_for_content(queryset.model):
        queryset = queryset.prefetch_related("versions", "versions__created_by")
    return queryset


def version_attr(func):
    def inner(obj):
        if get_versionable_for_content(obj):
            return func(obj.versions.all()[0])
    return inner


class ReferencesCMSAppConfig(CMSAppConfig):
    djangocms_references_enabled = True
    reference_extra_columns = [
        (
            (
                (version_attr(lambda v: v.get_state_display()), _("Status")),
                (version_attr(lambda v: v.created_by), _("Author")),
                (version_attr(lambda v: v.modified), _("Modified date")),
            ),
            version_queryset_modifier,
        )
    ]
