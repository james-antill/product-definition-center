# -*- coding: utf-8 -*-
#
# Copyright (c) 2015 Red Hat
# Licensed under The MIT License (MIT)
# http://opensource.org/licenses/MIT
#
import json
import os.path

from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase
from rest_framework import status

rpms_json_path = os.path.join(os.path.dirname(__file__), "test_tree.json"))
rpms_json = open(rpms_json_path, "r").read()

class TreeAPITestCase(APITestCase):
    def test_create_unreleasedvariant(self):
        url = reverse('unreleasedvariant-list')
        data = { 'variant_id': "core", 'variant_uid': "Core", 'variant_name': "Core", 'variant_version': "0-1", 'variant_type': 'module'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_tree(self):
        url = reverse('unreleasedvariant-list')
        data = { 'variant_id': "shells", 'variant_uid': "Shells", 'variant_name': "Shells", 'variant_version': "0-1", 'variant_type': 'module'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('tree-list')
        data = { 'tree_id': "Shells-x86_64-20160529.0", 'tree_date': "2016-05-29", 'variant': {"variant_uid": "Shells", "variant_version": "0-1"}, 'arch': "x86_64", 'content_format': ['rpm',], 'content': {'rpm' : json.dumps(json.loads(rpms_json))}, 'url': "/mnt/test/location"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
