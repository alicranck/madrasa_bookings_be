from sqlalchemy import inspect


def _convert_query_results_to_dict(query_result):

    def object_as_dict(obj):
        return {c.key: getattr(obj, c.key)
                for c in inspect(obj).mapper.column_attrs}

    return [object_as_dict(r) for r in query_result]
