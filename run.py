"""
Create events for upcoming games.

todo:
 - check for events before adding duplicates
 - ensure/add/remove attendees separately since they may be added after event is created
"""

import sys

from use_cases.main_entry import MainEntry


def main():
    param = sys.argv[1].lower() if len(sys.argv) > 1 else "ny urban"
    me = MainEntry()
    me.execute(param)


if __name__ == "__main__":
    main()
