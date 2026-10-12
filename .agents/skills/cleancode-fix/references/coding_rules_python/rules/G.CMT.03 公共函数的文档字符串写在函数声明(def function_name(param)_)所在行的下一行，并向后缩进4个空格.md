# G.CMT.03 公共函数的文档字符串写在函数声明(def function_name(param):)所在行的下一行，并向后缩进4个空格

- **规则ID**：dbf8e31c-86f9-4784-871c-d6203ca10c33
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

公共函数的文档字符串写在函数声明(def function_name(param):)所在行的下一行，并向后缩进4个空格。

**【正确示例】**

```
##### 场景1：函数的文档字符串缩进
- 修复示例：单行文档字符串
```python
def get_freeze_count(*args, **kwargs): # real signature unknown
    """ Return the number of objects in the permanent generation. """
    pass
```
- 修复示例：多行文档字符串的示例是采用的Google风格，也可以采用Pycharm reStructedText风格，只要项目组内的注释风格保持一致就可以
```python
def select_function(rlist, wlist, xlist, timeout=None):
    """Wait until one or more file descriptors are ready for some kind of I/O.
    
    If only one kind of condition is required, pass [] for the other lists.
    A file descriptor is either a socket or file object, or a small integer
    gotten from a fileno() method call on one of those.
    
    Args:
        rlist: wait until ready for reading
        wlist: wait until ready for writing
        xlist: wait for an ``exceptional condition''
    Return: 
    a tuple of three lists corresponding to the first three
        arguments; each contains the subset of the corresponding file descriptors
        that are ready.
    Optional parameters：
    specifies a timeout in seconds; it may be 
    a floating point number to specify fractions of seconds.  If it is absent
    or None, the call will never time out.

    Raises:
         IOErrorr:  An error...
    """
    pass
```

```
**【错误示例】**

```
##### 场景1：函数的文档字符串缩进
- 错误示例：文档字符串内容缩进不一致
```python
def func1(): 
"""
功能描述：
参数：
返回值：
异常描述：
:return:
"""
print("class three func 1")
```

```
**【修复建议】**

公共函数的文档字符串写在函数声明(def function_name(param):)所在行的下一行，并向后缩进4个空格。

1.使用单行文档字符串时，使用三引号作为定界符，前导三引号和结束三引号应该保持在同一行。

2.使用多行文档字符串时，使用三引号作为定界符，以前导三引号开头，结束三引号要自成一行。
