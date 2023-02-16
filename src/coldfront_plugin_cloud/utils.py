import re
from coldfront.core.allocation.models import (AllocationAttribute,
                                              AllocationAttributeType)


def env_safe_name(name):
    return name.replace(' ', '_').replace('-', '_').upper()


def set_attribute_on_allocation(allocation, attribute_type, attribute_value):
    allocation_attribute_type_obj = AllocationAttributeType.objects.get(
        name=attribute_type)
    try:
        attribute_obj = AllocationAttribute.objects.get(
            allocation_attribute_type=allocation_attribute_type_obj,
            allocation=allocation
        )
        attribute_obj.value = attribute_value
        attribute_obj.save()
    except AllocationAttribute.DoesNotExist:
        AllocationAttribute.objects.create(
            allocation_attribute_type=allocation_attribute_type_obj,
            allocation=allocation,
            value=attribute_value,
        )


def get_unique_project_name(project_name, max_length=None):

    valid_name = re.compile(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?')
    if valid_name.match(project_name) is None:
        assert False, "not a valid project name"

    # The random hex at the end of the project name is 6 chars, 1 hyphens
    max_without_suffix = max_length - 7 if max_length else None
    return f'{project_name[:max_without_suffix]}-f{secrets.token_hex(3)}'
