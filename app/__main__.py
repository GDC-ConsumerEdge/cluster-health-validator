import argparse
import logging
import sys
import time
from check_data_volumes import CheckDataVolumes
from check_google_group_rbac import CheckGoogleGroupRBAC
from check_nodes import CheckNodes
from check_robin_cluster import CheckRobinCluster
from check_root_syncs import CheckRootSyncs
from check_virtual_machines import CheckVirtualMachines
from check_vmruntime import CheckVMRuntime
from kubernetes import config

health_check_map = {
    CheckGoogleGroupRBAC.__name__.lower(): CheckGoogleGroupRBAC,
    CheckNodes.__name__.lower(): CheckNodes,
    CheckRobinCluster.__name__.lower(): CheckRobinCluster,
    CheckRootSyncs.__name__.lower(): CheckRootSyncs,
    CheckVMRuntime.__name__.lower(): CheckVMRuntime,
    CheckDataVolumes.__name__.lower(): CheckDataVolumes,
    CheckVirtualMachines.__name__.lower(): CheckVirtualMachines,
}

default_health_checks = [
    CheckNodes.__name__.lower(),
    CheckRobinCluster.__name__.lower(),
    CheckRootSyncs.__name__.lower()
]

config.load_config()
logging.basicConfig(stream=sys.stdout)
logger = logging.getLogger('main')

def run_health_checks(args):
    checks = []

    if args.health_check is None:
        # use default health checks
        logger.info('No health checks specified, using default health checks: ' + ', '.join(default_health_checks))
        checks = [health_check_map[check_name]() for check_name in default_health_checks]
    else:
        for health_check in args.health_check:
            if len(health_check) == 0:
                logger.error('No health check specified')
                return 1

            check_name = health_check[0].lower()

            if check_name not in health_check_map:
                logger.error('Unknown health check specified: ' + health_check)
                return 1
            
             
            if len(health_check) > 1:
                # Health check includes named parameters that need to be passed
                check_args = {}

                for parameter in health_check[1:]:
                    if "=" not in parameter:
                        logger.error('Invalid parameter specified: ' + parameter + '. Parameters must be in the format key=value')
                        return 1

                    key, value = parameter.split("=")
                    check_args[key] = value

                checks.append(health_check_map[check_name](check_args))
            else:
                checks.append(health_check_map[check_name]())

    failed_health_checks = []

    for check in checks:
        try:
            if not check.is_healthy():
                failed_health_checks.append(check.__class__.__name__)
        except Exception:
            failed_health_checks.append(check.__class__.__name__)


    if len(failed_health_checks) > 0:
        for failure in failed_health_checks:
            logger.error('Health check failed: ' + failure)
        return 1
    
    logger.info('All health checks passed!')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--health-check',
        action='append',
        help='''Set a health check to perform.
                For health checks requiring parameters, pass them in a key=value format as additional arguments.
                Example: --health-check checkvirtualmachines namespace=vm-workloads count=3''',
        nargs='+')
    verbosity_mutex = parser.add_mutually_exclusive_group()
    verbosity_mutex.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='increase output verbosity; -vv for max verbosity')
    verbosity_mutex.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='output errors only')

    parser.add_argument(
        '-w', '--wait',
        action='store_true',
        help='wait for health checks to pass before exiting')

    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=60,
        help='interval to poll passing health checks')

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=3600,
        help='Overall timeout for health checks to pass')

    args = parser.parse_args()
    if args.quiet:
        logger.setLevel(logging.ERROR)
    elif args.verbose == 1:
        logger.setLevel(logging.INFO)
    elif args.verbose >= 2:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    if (args.wait):
        # Poll continuously unless all health checks pass
        max_loops = int(args.timeout / args.interval)
        for i in range(max_loops):
            if run_health_checks(args) == 0:
                return 0

            time.sleep(args.interval)

        logger.error('Timed out waiting for health checks to pass')
        return 1
    else:
        return run_health_checks(args)

if __name__ == '__main__':
    sys.exit(main())