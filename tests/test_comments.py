from types import SimpleNamespace as N

from nopanic.comments import Limits, context_of


def msg(parent):
    return N(reply_to_message=parent)


def test_context_only_for_post_or_bot_thread():
    post = N(text="Пост", caption=None, is_automatic_forward=True, from_user=None)
    bot_ans = N(text="Відповідь", caption=None, is_automatic_forward=False, from_user=N(id=42))
    human = N(text="Інший коментар", caption=None, is_automatic_forward=False, from_user=N(id=7))
    assert context_of(msg(post), 42).startswith("Channel post")
    assert context_of(msg(bot_ans), 42).startswith("Your earlier answer")
    assert context_of(msg(human), 42) is None
    assert context_of(msg(None), 42) is None


def test_limits_per_user():
    lim = Limits()
    assert [lim.allow(1) for _ in range(4)] == [True, True, True, False]
    assert lim.allow(2)
