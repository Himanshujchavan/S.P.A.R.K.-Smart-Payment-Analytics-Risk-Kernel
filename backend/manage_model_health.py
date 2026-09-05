# manage_model_health.py
# CLI Management script for S.P.A.R.K. model health operations.
#
# Usage:
#   python manage_model_health.py check-drift
#   python manage_model_health.py check-drift --version spark-xgb-v3.1.0

import argparse
import logging
import sys

# Ensure backend is in path
import os
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from api.services.drift_service import drift_service, DriftService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [health-mgr] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="S.P.A.R.K. Model Health Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-drift command
    drift_parser = subparsers.add_parser("check-drift", help="Run a PSI drift check")
    drift_parser.add_argument("--version", type=str, help="Model version to check")

    args = parser.parse_args()

    if args.command == "check-drift":
        try:
            service = drift_service
            if args.version:
                service = DriftService(model_version=args.version)

            result = service.run_check()
            print("\n" + "="*40)
            print(f" DRIFT CHECK RESULT")
            print("-" * 40)
            print(f" Status:  {result['status']}")
            print(f" PSI:     {result['psi']}")
            print(f" Message:  {result['message']}")
            print("="*40 + "\n")
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
