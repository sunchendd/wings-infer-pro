# G.PRM.03 资源的申请和释放需要成对使用，包括正常和异常场景

- **规则ID**：6c03ffa6-9f5f-4505-8e2d-44a50503a93a
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

文件、sockets或其他类似文件的对象在打开时会消耗有限的系统资源, 如文件描述符。如果这些资源在使用后没有及时归还系统, 那么用于处理这些对象的代码会将资源消耗殆尽。持有文件行为也将会阻止对于文件的其他诸如移动、删除之类的操作。

仅仅是从逻辑上关闭文件和sockets, 那么它们仍然可能会被其共享的程序在无意中进行读或者写操作。只有当它们真正被关闭后, 对于它们尝试进行读或者写操作才会抛出异常, 并使得问题快速显现出来。



因此，有以下几条建议：

1.在文件和sockets等等类似资源使用结束时, 显式的关闭它；

2.关闭的位置建议和打开的代码位置同函数/方法、同一个类、或同一个模块文件，不推荐跨模块文件代码管理资源；

3.异常场景建议在try/except/finally结构的finally代码块中关闭资源。



推荐使用with/as语句结合上下文管理器对资源对象进行管理。

**【正确示例】**

```
【正例1】在一个函数上下文中关闭使用结束后的文件。
import logging


logger = logging.getLogger(__file__)


def show_notebook(notebook_path: str):
    notebook = None
    try:
        notebook = open(notebook_path, 'r')
    except IOError as e:
        logger.error(e)

    if notebook:
        for line in notebook:
            print(line)

        notebook.close()  # 文件使用结束后显式关闭

【正例2】支持上下文管理器功能的对象推荐使用with/as语句。
with open('hello.txt', 'a+') as hello_file:
    for line in hello_file:
        print(line)

【正例3】对于不支持使用with/as语句的对象,使用contextlib.closing()。
import contextlib


with contextlib.closing(urllib.urlopen('http://www.python.org/')) as front_page:
    for line in front_page:
        print(line)

【正例4】保证在正常或异常场景关闭资源。
handle = None
try:
    handle = open(r'example_data.txt') 
    data = handle.read() 
except UnicodeDecodeError as decode_error:
    print(decode_error)
except IOError as io_error:
    print(io_error)
finally:
    if handle:
        handle.close()  # finally代码块中的代码总能保证资源释放

```
**【错误示例】**

```
# 在函数中打开文件，但在函数上下文结束时未显式关闭文件。
import logging


logger = logging.getLogger(__file__)


def show_notebook(notebook_path: str):
    notebook = None
    try:
        notebook = open(notebook_path, 'r')
    except IOError as e:
        logger.error(e)

    if notebook:
        for line in notebook:
            print(line)

```
**【修复建议】**
