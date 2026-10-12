# G.TES.01 禁止在生产版本的业务代码中使用assert

- **规则ID**：3c1fb185-b0d7-41d3-9e34-4693d91f44fa
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

在编译时编译优化参数如果大于等于1，编译器就会删除assert语句。

如果在业务代码中使用了assert语句做了一些特殊的业务匹配，同时使用了编译优化，则可能会发生出现不可预期的结果。

所以assert语句通常只在测试代码中使用，禁止在生产版本的业务代码中使用assert，具体的关于assert的信息可以查看官方介绍。

比如有如下代码，希望此代码仅在Linux环境执行：

import sys





def check_system():

    assert ("linux" in sys.platform), "Code is Linux only"





check_system()



如果代码没有做编译优化，在windows环境上执行会报如下错误：

 Traceback (most recent call last):

   File "./demo.py", line 8, in <module>

     check_system()

   File "./demo.py", line 5, in check_system

     assert ('linux' in sys.platform), "Code is Linux only"

 AssertionError: Code is Linux only



使用如下参数编译这个文件：

import compileall





compileall.compile_file("./demo.py", optimize=1)



再在windows上执行编译之后的代码，则不会报任何错误。

另：使用uncompyle6反编译代码，会得到编译优化之后的代码，如下：

import sys





def check_system():

    pass





check_system()



如果需要在业务代码中做类似的检查，建议使用常规的判断。

**【正确示例】**

```
import sys


class NotSupportedError(Exception):
    def __str__(self):
        return "Code is Linux only"


def check_system():
    if "linux" in sys.platform:
        return
    raise NotSupportedError()


check_system()

```
**【错误示例】**

```
import sys


def check_system():
    assert ("linux" in sys.platform), "Code is Linux only"


check_system()

```
**【修复建议】**
