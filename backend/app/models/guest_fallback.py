"""What happens to a staff member's +1 guest, and to them, if the guest has no pass."""


class GuestFallback:
    """Values of ``guest_fallback`` on passes, lottery entries and alternate entries."""

    # The guest is dropped and the staff member attends alone.
    ATTEND_ALONE = "attend_alone"
    # The staff member's pass is released too. In the alternate queue, the staff
    # member is skipped until there's a pass for both of them.
    RELEASE = "release"
    # The guest waits on the alternate list. The staff member attends either way.
    WAIT = "wait"
    # The guest waits on the alternate list. If they're still waiting when the show
    # closes, the staff member's pass is released.
    WAIT_THEN_RELEASE = "wait_then_release"
