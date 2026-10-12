import argparse
import time
import logging
import numpy as np
from mooncake.store import MooncakeDistributedStore
import signal
import os
import threading


# Disable memcpy optimization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('stress_cluster_benchmark')

class GlobalTE:
    def __init__(self):
        self.transfer_engine = None
        self.is_register_buffer: bool = False
        self.transfer_engine_lock = threading.Lock()
        self.register_buffer_lock = threading.Lock()

    def get_transfer_engine(self, hostname: str, device_name: str | None):
        if self.transfer_engine is None:
            with self.transfer_engine_lock:
                # Double-Checked Locking
                if self.transfer_engine is None:
                    try:
                        from mooncake.engine import TransferEngine  # type: ignore
                    except ImportError as e:
                        raise ImportError(
                            "Please install mooncake by following the instructions at "
                            "https://github.com/kvcache-ai/Mooncake/blob/main/doc/en/build.md "  # noqa: E501
                            "to run vLLM with MooncakeConnector."
                        ) from e
                    self.transfer_engine = TransferEngine()
                    device_name = device_name if device_name is not None else ""
                    ret_value = self.transfer_engine.initialize(hostname, "P2PHANDSHAKE", "ascend", device_name)
                    if ret_value != 0:
                        raise RuntimeError(f"TransferEngine initialization failed with ret_value: {ret_value}")
        return self.transfer_engine

    def register_buffer(self, ptrs: list[int], sizes: list[int]):
        with self.register_buffer_lock:
            assert self.transfer_engine is not None, "Transfer engine must be initialized"
            if self.is_register_buffer:
                return
            for ptr, size in zip(ptrs, sizes):
                ret_value = self.transfer_engine.register_memory(ptr, size)
                if ret_value != 0:
                    raise RuntimeError("Mooncake memory registration failed.")
            self.is_register_buffer = True

global_te = GlobalTE()

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

        transfer_engine = global_te.get_transfer_engine(local_hostname, device_name=None)
        local_hostname = local_hostname + ":" + str(transfer_engine.get_rpc_port())

        logger.info(f"  local_hostname: {local_hostname}")

        if self.args.offload_dir == "":
            retcode = self.store.setup(local_hostname, metadata_server, global_segment_size,
                                  local_buffer_size, protocol, device_name, master_server_address, transfer_engine.get_engine())
        else:
            retcode = self.store.setup(local_hostname, metadata_server, global_segment_size,
                                  local_buffer_size, protocol, device_name, master_server_address, transfer_engine.get_engine(), True, self.args.offload_dir)

        if retcode:
            logger.error(f"Store setup failed with return code {retcode}")
            exit(1)

        # Allocate and register memory buffer using numpy for better performance
        buffer_size = 1024 * 1024 * 4
        # 使用 Ascend aclrtMallocHost 分配内存
        buffer_ptr = ctypes.c_void_p()
        ret = acl_lib.aclrtMallocHost(ctypes.byref(buffer_ptr), buffer_size)
        if ret != 0:
            logger.error(f"aclrtMallocHost failed with return code {ret}")
            exit(1)

        self.buffer_ptr = buffer_ptr.value

        # 包装为 numpy array（方便后续操作）
        self.buffer_array = np.ctypeslib.as_array(
            ctypes.cast(buffer_ptr, ctypes.POINTER(ctypes.c_uint8)),
            shape=(buffer_size,)
        )

        retcode = self.store.register_buffer(self.buffer_ptr, buffer_size)
        if retcode:
            logger.error(f"Buffer registration failed with return code {retcode}")
            exit(1)

        logger.info(f"Allocated and registered {buffer_size // (1024*1024)} MB buffer for zero-copy operations")
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

    import ctypes
    acl_lib = ctypes.CDLL('libascendcl.so')
    acl_lib.aclInit(None)
    acl_lib.aclrtSetDevice(0)

# 可能需要额外调用 aclrtCreateContext 或等待设备就绪
# 尝试加一行延迟
    import time
    time.sleep(2)
    try:
        mooncake_store = MooncakeInstance(args)
        mooncake_store.setup()

        logger.info("Test completed successfully!")

    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise

    print(f" Mooncake Store Daemon is running，PID: {os.getpid()}")
    # 阻塞等待信号（Ctrl+C / kill 命令可终止）
    signal.pause()

if __name__ == '__main__':
    try:
        import ctypes
        acl_lib = ctypes.CDLL('libascendcl.so')
        acl_lib.aclInit(None)
        acl_lib.aclrtSetDevice(0)
    except Exception:
        pass
    main()
