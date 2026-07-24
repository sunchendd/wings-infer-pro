#!/usr/bin/env bash
# memcache MetaService daemon(仅 master 节点起;framework 自动 bash <path> &,不监听端口)。
python -c "from memcache_hybrid import MetaService; MetaService.main()"
