#
# Copyright (c) 2015 Red Hat
# Licensed under The MIT License (MIT)
# http://opensource.org/licenses/MIT
#
import json

from rest_framework import mixins, viewsets, status
from rest_framework.response import Response

from . import models
from . import serializers
from . import filters
from pdc.apps.common.viewsets import (ChangeSetCreateModelMixin, StrictQueryParamMixin,
                                      ChangeSetUpdateModelMixin, ChangeSetDestroyModelMixin)
from pdc.apps.release.models import Release
from pdc.apps.common import hacks
from pdc.apps.common.serializers import StrictSerializerMixin


class RepoViewSet(ChangeSetCreateModelMixin,
                  ChangeSetUpdateModelMixin,
                  ChangeSetDestroyModelMixin,
                  StrictQueryParamMixin,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  viewsets.GenericViewSet):
    """
    An API endpoint providing access to repositories.
    """
    queryset = models.Repo.objects.all().select_related()
    serializer_class = serializers.RepoSerializer
    filter_class = filters.RepoFilter

    def create(self, *args, **kwargs):
        """
        __Method__: `POST`

        __URL__: `/repos/`

        __Data__:

            {
                release_id:       string,
                variant_uid:      string,
                arch:             string,
                service:          string,
                repo_family:      string,
                content_format:   string,
                content_category: string,
                name:             string,
                shadow:           bool,      (OPTIONAL, default False)
                product_id:       int        (OPTIONAL)
            }

        There are additional validations for the repository name for specific
        content category. If and only if the content category is `debug`, the
        name must contain `debug` substring.

        The name must also match type of associated release by having a
        specific substring.

            release type  | name substring
            --------------+---------------
            fast          | -fast
            eus           | .z
            aus           | .aus or .ll
            els           | els

        __Response__: Same as input data.
        """
        return super(RepoViewSet, self).create(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: `GET`

        __URL__: `/repos/`

        __Query params__:

          * `arch`
          * `content_category`
          * `content_format`
          * `name`
          * `release_id`
          * `repo_family`
          * `service`
          * `shadow` (possible values are `True` and `False`)
          * `variant_uid`
          * `product_id`

        __Response__:

            {
                id:               int,
                release_id:       string,
                variant_uid:      string,
                arch:             string,
                service:          string,
                repo_family:      string,
                content_format:   string,
                content_category: string,
                name:             string,
                shadow:           bool,
                product_id:       int
            }
        """
        return super(RepoViewSet, self).list(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        __Method__: `PUT`, `PATCH`

        __URL__: `/repos/{id}`

        __Data__:

            {
                release_id:       string,
                variant_uid:      string,
                arch:             string,
                service:          string,
                repo_family:      string,
                content_format:   string,
                content_category: string,
                name:             string,
                shadow:           bool,     # optional, default False
                product_id:       int       # optional
            }

        __Response__:

            {
                id:               int,
                release_id:       string,
                variant_uid:      string,
                arch:             string,
                service:          string,
                repo_family:      string,
                content_format:   string,
                content_category: string,
                name:             string,
                shadow:           bool,
                product_id:       int
            }
        """
        return super(RepoViewSet, self).update(*args, **kwargs)

    def destroy(self, *args, **kwargs):
        """
        __Method__: `DELETE`

        __URL__: /repos/{id}
        """
        return super(RepoViewSet, self).destroy(*args, **kwargs)


class RepoCloneViewSet(StrictQueryParamMixin, viewsets.GenericViewSet):
    queryset = models.Repo.objects.none()   # Required for permissions

    def create(self, request):
        """
        Clone all repositories from one release under another release.

        The call is atomic, i.e. either all repositories are cloned or nothing
        is done.

        If the source and target releases do not have the same variants, the
        cloning will silently ignore repositories with Variant.Arch that is
        present in source release but not in target release. It is not a
        problem if the target release has additional variants.

        __Method__: `POST`

        __URL__: `/rpc/repos/clone/`


        __Data__:

            {
                "release_id_from":          string,
                "release_id_to":            string
                "include_service":          [string],   # optional
                "include_repo_family":      [string],   # optional
                "include_content_format":   [string],   # optional
                "include_content_category": [string],   # optional
                "include_shadow":           bool,       # optional
                "include_product_id":       int         # optional
            }

        The `include_*` keys are used to filter which releases should be
        cloned. If any key is omitted, all values for that attribute will be
        cloned.

        __Response__:
        The call returns a list of repositories created under target release.

            [
              {
                "shadow":           bool,
                "release_id":       string,
                "variant_uid":      string,
                "arch":             string,
                "service":          string,
                "repo_family":      string,
                "content_format":   string,
                "content_category": string,
                "name":             string,
                "product_id":       int
              },
              ...
            ]
        """
        data = request.data
        keys = set(['release_id_from', 'release_id_to'])
        arg_filter_map = {'include_service': ('service__name__in', hacks.as_list),
                          'include_repo_family': ('repo_family__name__in', hacks.as_list),
                          'include_content_format': ('content_format__name__in', hacks.as_list),
                          'include_content_category': ('content_category__name__in', hacks.as_list),
                          'include_shadow': ('shadow', hacks.convert_str_to_bool),
                          'include_product_id': ('product_id', hacks.convert_str_to_int)}
        allowed_keys = list(keys) + arg_filter_map.keys()

        missing_keys = keys - set(data.keys())
        if missing_keys:
            errors = dict([(k, ['This field is required.']) for k in missing_keys])
            return Response(status=status.HTTP_400_BAD_REQUEST, data=errors)
        extra_keys = set(data.keys()) - set(allowed_keys)
        StrictSerializerMixin.maybe_raise_error(extra_keys)

        kwargs = {
            'variant_arch__variant__release__release_id': data['release_id_from']
        }

        for arg, (filter, transform) in arg_filter_map.iteritems():
            arg_data = request.data.get(arg)
            if arg_data:
                kwargs[filter] = transform(arg_data, name=arg)

        repos = models.Repo.objects.filter(**kwargs)
        if not repos:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'detail': 'No repos to clone (or source release does not exist).'})

        try:
            target_release = Release.objects.get(release_id=data['release_id_to'])
        except Release.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND,
                            data={'detail': 'Target release %s does not exist.' % data['release_id_to']})

        # Skip repos from nonexisting trees.
        repos = [repo for repo in repos if repo.tree in target_release.trees]

        serializer = serializers.RepoSerializer(repos, many=True)
        copy = serializer.data
        for repo in copy:
            repo['release_id'] = target_release.release_id
        new_repos = serializers.RepoSerializer(data=copy, many=True)
        if not new_repos.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'detail': dict((repo['name'], err)
                                                 for repo, err in zip(copy, new_repos.errors)
                                                 if err)})
        for raw_repo, repo_obj in zip(copy, new_repos.save()):
            request.changeset.add('Repo', repo_obj.pk,
                                  'null', json.dumps(raw_repo))

        return Response(status=status.HTTP_200_OK, data=copy)


class RepoFamilyViewSet(StrictQueryParamMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    """
    ##Overview##

    This page shows the usage of the **RepoFamily API**, please see the
    following for more details.

    ##Test tools##

    You can use ``curl`` in terminal, with -X _method_ (GET|POST|PUT|PATCH|DELETE),
    -d _data_ (a json string). or GUI plugins for
    browsers, such as ``RESTClient``, ``RESTConsole``.
    """
    queryset = models.RepoFamily.objects.all()
    serializer_class = serializers.RepoFamilySerializer
    filter_class = filters.RepoFamilyFilter

    def list(self, request, *args, **kwargs):
        """
        __Method__: `GET`

        __URL__: `/repo-families/`

        __Query params__:

          * `name` (support LIKE)

        __Response__:

            {
                "count": int,
                "next": url,
                "previous": url,
                "results": [
                    {
                        "name": string,
                        "description": string
                    },
                    ...
                ]
            }

        __Example__:

            $ curl  "%(HOST_NAME)s/%(API_PATH)s/repo-families/
            {
                "count": 3,
                "next": null,
                "previous": null,
                "results": [
                    {
                        "name": "dist",
                        "description": "Production repositories"
                    },
                    {
                        "name": "beta",
                        "description": "Beta (pre-production) repositories"
                    },
                    {
                        "name": "htb",
                        "description": "Repositories for High Touch Beta (HTB) customers"
                    }
                ]
            }
        """
        return super(RepoFamilyViewSet, self).list(request, *args, **kwargs)