import inspect

from sentinai.llm.base import LLMProvider


def test_stream_is_declared_as_returning_an_iterator_not_a_coroutine():
    assert not inspect.iscoroutinefunction(LLMProvider.stream)
