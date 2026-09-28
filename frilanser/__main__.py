"""اجرا با دستور python -m frilanser"""

import sys

from frilanser.cli import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nاجرا لغو شد.")
        sys.exit(130)
