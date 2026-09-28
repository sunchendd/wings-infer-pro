import argparse
import time
import logging
from mooncake.store import MooncakeDistributedStore
import signal
import os


# Disable memcpy optimization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('stress_cluster_benchmark')


class MooncakeInstance:
    def __init__(self, args):
        self.args = args
        self.store = None
        self.buffer_array = None
        self.buffer_ptr = None

    def setup(self):
        """Initialize the MooncakeDistributedStore and allocate registered memory."""

        self.store = MooncakeDistributedStore()

        # Setup store
        protocol = self.args.protocol
        device_name = self.args.device_name
        local_hostname = self.args.local_hostname
        metadata_server = self.args.metadata_server
        global_segment_size = self.args.global_segment_size * 1024 * 1024
        local_buffer_size = self.args.local_buffer_size * 1024 * 1024
        master_server_address = self.args.master_server

        logger.info(f"  Protocol: {protocol}, Device: {device_name}")
        logger.info(f"  Global segment: {global_segment_size // (1024*1024)} MB")
        logger.info(f"  Local buffer: {local_buffer_size // (1024*1024)} MB")

        if self.args.offload_dir == "":
            retcode = self.store.setup(local_hostname, metadata_server, global_segment_size,
                                  local_buffer_size, protocol, device_name, master_server_address)
        else:
            retcode = self.store.setup(local_hostname, metadata_server, global_segment_size,
                                  local_buffer_size, protocol, device_name, master_server_address, None, True, self.args.offload_dir)

        if retcode:
            logger.error(f"Store setup failed with return code {retcode}")
            exit(1)

        time.sleep(1)

def parse_arguments():
    """Parse command-line arguments for the stress test."""
    parser = argparse.ArgumentParser(
        description="Mooncake Distributed Store Process",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Network and connection settings
    parser.add_argument("--protocol", type=str, default="rdma", help="Communication protocol to use")
    parser.add_argument("--device-name", type=str, default="erdma_0", help="Network device name for RDMA")
    parser.add_argument("--local-hostname", type=str, default="localhost", help="Local hostname")
    parser.add_argument("--metadata-server", type=str, default="http://127.0.0.1:8080/metadata", help="Metadata server address")
    parser.add_argument("--master-server", type=str, default="localhost:50051", help="Master server address")

    # Memory and storage settings
    parser.add_argument("--global-segment-size", type=int, default=10000, help="Global segment size in MB")
    parser.add_argument("--local-buffer-size", type=int, default=0, help="Local buffer size in MB")

    # New parameters
    parser.add_argument("--offload-dir", type=str, default="", help="offload directory")

    return parser.parse_args()

def main():
    """Main entry point for the stress test."""
    args = parse_arguments()

    logger.info("=== Mooncake Store ===")
    logger.info(f"Protocol: {args.protocol}")
    logger.info("=" * 50)
    logger.info(f"offload directory: {args.offload_dir}")

    try:
        mooncake_store = MooncakeInstance(args)
        mooncake_store.setup()

    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise

    print(f" Mooncake Store Daemon is running，PID: {os.getpid()}")
    # 阻塞等待信号（Ctrl+C / kill 命令可终止）
    signal.pause()

if __name__ == '__main__':
    main()

