import logging
import time

from memcache_hybrid import DistributedObjectStore


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    store = DistributedObjectStore()
    res = store.init(0)
    if res != 0:
        logger.error("Failed to init memcache, res = %s", res)
        raise SystemExit(1)
    logger.info("MemCache init success.")

    while True:
        time.sleep(1)
