#!/usr/bin/env python3
"""웹 UI용 KCI 실시간 검색 로컬 프록시(얇은 실행 셸).

실제 로직은 패키지의 literature_review.web_proxy 에 있다. 설치 후에는
``lr-kci-proxy`` 명령으로도 동일하게 실행할 수 있다.

    KCI_API_KEY=... python scripts/kci_proxy.py --port 8765
"""

from literature_review.web_proxy import main

if __name__ == "__main__":
    main()
