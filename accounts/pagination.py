from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class DynamicPagination(LimitOffsetPagination):

    default_limit = 3
    max_limit = 1000

    def get_paginated_response(self, data):

        return Response({
            'count': self.count,

            'has_next': self.get_next_link() is not None,

            'has_previous': self.get_previous_link() is not None,

            'limit': self.limit,

            'offset': self.offset,

            'results': data
        })