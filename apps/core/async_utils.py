import functools

from asgiref.sync import sync_to_async


def service(func):
    """Turn a synchronous service function into an awaitable one.

    Django cannot run `transaction.atomic()` or `select_for_update()` across separate awaited
    ORM calls, so each service stays ONE synchronous unit of work and is run in a worker thread
    as a whole. That keeps every transaction and row lock correct while views stay async.

        await checkin.check_in(...)        # from async views
        checkin.check_in.sync(...)         # from Celery tasks, management commands, other services
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await sync_to_async(func, thread_sensitive=True)(*args, **kwargs)

    wrapper.sync = func  # pyright: ignore[reportAttributeAccessIssue]
    return wrapper