"""
The parts of the app that scheduled jobs and audit log entries belong to, as
shown in KALX Staff Admin.

Promotions admins see only the pass giveaway's audit log entries, so common
code needs its area's name too.
"""

COMMON_AREA = "Common"
PASS_GIVEAWAY_AREA = "Radio Pass Giveaway"
WORKFORMS_AREA = "KALX Workforms"
SHORT_LINKS_AREA = "Short Links"
DIRECTORY_AREA = "KALX Staff Directory"

AREAS = [
    COMMON_AREA,
    PASS_GIVEAWAY_AREA,
    WORKFORMS_AREA,
    SHORT_LINKS_AREA,
    DIRECTORY_AREA,
]
