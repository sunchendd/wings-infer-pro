# G.LOG.02 使用日志记录工具实现日志功能

- **规则ID**：2a2c1da4-1df5-410d-b478-03508a449993
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

使用标准输出（print）或标准输出（sys.stdout.write），会导致难以监控程序运行状况。

建议：采用专门的日志记录工具或模块（如：logging）。

**【正确示例】**

```
import logging
import threading
import time


logging.basicConfig("xxx")  # 指定日志文件路径等


need_exit = False


class MyThread(threading.Thread):
    def __init__(self, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        logging.info("Starting: %s", self.name)  # 采用正确的级别及形式记录日志
        process_something(self.name, self.counter, 5)
        logging.info("Exiting:%s", self.name)


def process_something(thread_name, delay, counter):
    while counter:
        if need_exit:
            threading.Thread.exit()

        logging.debug("%s: %s", thread_name, time.ctime(time.time()))
        counter -= 1

```
**【错误示例】**

```
import threading


class MyThread(threading.Thread):
    def __init__(self, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        print("Starting " + self.name)
        process_something(self.name, self.counter, 5)
        print("Exiting " + self.name)

```
**【修复建议】**

1、采用logging模块记录日志；

2、定义独立的日志记录文件；

3、选择正确的日志级别记录日志；
