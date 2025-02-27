import os
import time
import unittest

from coldfront_plugin_cloud import attributes, openshift, tasks, utils
from coldfront_plugin_cloud.tests import base


@unittest.skipUnless(os.getenv('FUNCTIONAL_TESTS'), 'Functional tests not enabled.')
class TestAllocation(base.TestBase):

    def setUp(self) -> None:
        super().setUp()
        self.resource = self.new_openshift_resource(
            name='Microshift',
            auth_url=os.getenv('OS_AUTH_URL')
        )

    def test_new_allocation(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 1)
        allocator = openshift.OpenShiftResourceAllocator(self.resource,
                                                         allocation)

        tasks.activate_allocation(allocation.pk)
        allocation.refresh_from_db()

        # Check project
        project_id = allocation.get_attribute(attributes.ALLOCATION_PROJECT_ID)
        self.assertIsNotNone(project_id)
        self.assertIsNotNone(allocation.get_attribute(attributes.ALLOCATION_PROJECT_NAME))

        allocator._get_project(project_id)

        # Check user and roles
        allocator.get_federated_user(user.username)

        allocator._get_role(user.username, project_id)

        allocator.remove_role_from_user(user.username, project_id)

        with self.assertRaises(openshift.NotFound):
            allocator._get_role(user.username, project_id)

        allocator.disable_project(project_id)

        # Deleting a project is not instantaneous on OpenShift
        time.sleep(10)
        with self.assertRaises(openshift.NotFound):
            allocator._get_project(project_id)

    def test_add_remove_user(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        project_user = self.new_project_user(user, project)
        allocation = self.new_allocation(project, self.resource, 1)
        allocation_user = self.new_allocation_user(allocation, user)
        allocator = openshift.OpenShiftResourceAllocator(self.resource,
                                                         allocation)

        user2 = self.new_user()
        project_user2 = self.new_project_user(user2, project)
        allocation_user2 = self.new_allocation_user(allocation, user2)

        tasks.activate_allocation(allocation.pk)
        allocation.refresh_from_db()

        project_id = allocation.get_attribute(attributes.ALLOCATION_PROJECT_ID)

        tasks.add_user_to_allocation(allocation_user2.pk)
        allocator._get_role(user.username, project_id)

        allocator.get_federated_user(user2.username)

        allocator._get_role(user.username, project_id)
        allocator._get_role(user2.username, project_id)

        tasks.remove_user_from_allocation(allocation_user2.pk)

        allocator._get_role(user.username, project_id)
        with self.assertRaises(openshift.NotFound):
            allocator._get_role(user2.username, project_id)

    def test_new_allocation_quota(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 2)
        allocator = openshift.OpenShiftResourceAllocator(self.resource,
                                                         allocation)

        tasks.activate_allocation(allocation.pk)
        allocation.refresh_from_db()

        project_id = allocation.get_attribute(attributes.ALLOCATION_PROJECT_ID)

        self.assertEqual(allocation.get_attribute(attributes.QUOTA_LIMITS_CPU), 2 * 2)
        self.assertEqual(allocation.get_attribute(attributes.QUOTA_LIMITS_MEMORY), 2 * 2048)
        self.assertEqual(allocation.get_attribute(attributes.QUOTA_LIMITS_EPHEMERAL_STORAGE_GB), 2 * 5)

        quota = allocator.get_quota(project_id)['Quota']
        quota = {k: v for k, v in quota.items() if v is not None}
        # The return value will update to the most relevant unit, so
        # 4000m cores becomes 4 and 4096Mi becomes 4Gi
        self.assertEqual(quota, {
            ":limits.cpu": "4",
            ":limits.memory": "4Gi",
            ":limits.ephemeral-storage": "10Gi",
        })

    def test_reactivate_allocation(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 2)
        allocator = openshift.OpenShiftResourceAllocator(self.resource,
                                                         allocation)

        tasks.activate_allocation(allocation.pk)
        allocation.refresh_from_db()

        project_id = allocation.get_attribute(attributes.ALLOCATION_PROJECT_ID)

        self.assertEqual(allocation.get_attribute(attributes.QUOTA_LIMITS_CPU), 4)

        quota = allocator.get_quota(project_id)['Quota']

        # https://github.com/CCI-MOC/openshift-acct-mgt
        quota = {k: v for k, v in quota.items() if v is not None}
        # The return value will update to the most relevant unit, so
        # 4000m cores becomes 4 and 4096Mi becomes 4Gi
        self.assertEqual(quota, {
            ":limits.cpu": "4",
            ":limits.memory": "4Gi",
            ":limits.ephemeral-storage": "10Gi",
        })

        # Simulate an attribute change request and subsequent approval which
        # triggers a reactivation
        utils.set_attribute_on_allocation(allocation, attributes.QUOTA_LIMITS_CPU, 3)
        tasks.activate_allocation(allocation.pk)
        allocation.refresh_from_db()

        quota = allocator.get_quota(project_id)['Quota']
        quota = {k: v for k, v in quota.items() if v is not None}
        # The return value will update to the most relevant unit, so
        # 4000m cores becomes 4 and 4096Mi becomes 4Gi
        self.assertEqual(quota, {
            ":limits.cpu": "3",
            ":limits.memory": "4Gi",
            ":limits.ephemeral-storage": "10Gi",
        })

        allocator._get_role(user.username, project_id)
