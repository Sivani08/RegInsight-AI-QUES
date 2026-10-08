"""Literal workspace search preserves the existing evidence browsing contract."""


def prepare_text_search(connection):
    return True


def prepare_metadata_search(connection):
    return None


def text_predicate(connection, search):
    return 'SELECT hash FROM texts WHERE strpos(lower(text),lower(%s))>0', [search]


def candidate_predicate(connection, search, run_id):
    # Domain substring search stays exact; semantic RAG is a separate explicit mode.
    return '', []
