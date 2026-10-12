# G.CMT.02 类的文档字符串写在类声明(class ClassName:)所在行的下一行，并向后缩进4个空格

- **规则ID**：009d924c-ff37-475a-a074-a446cb301490
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

类的文档字符串应位于类定义头部的下一行，相对于class关键字缩进4个空格，与内部定义的方法、数据成员具有相同的缩进量。

**【正确示例】**

```
### 场景1：类的文档字符串格式
- 修复示例：单行文档字符串
```python
class ErrorClass(Exception):
    """Base class for I/O related errors."""
    def __init__(self, *args, **kwargs): 
        pass
```
- 修复示例：多行文档字符串
```python
class ExampleClass:
    """The summary line for a class docstring should fit on one line.

    If the class has public attributes, they may be documented here
    in an ``Attributes`` section and follow the same formatting as a
    function's ``Args`` section. Alternatively, attributes may be documented
    inline with the attribute's declaration (see __init__ method below).

    Properties created with the ``@property`` decorator should be documented
    in the property's getter method.

    Attributes:
        attr1 (str): Description of `attr1`.
        attr2 (:obj:`int`, optional): Description of `attr2`.

    """
    def __init__(self, param1, param2, param3):
        """Example of docstring on the __init__ method.

        The __init__ method may be documented in either the class level
        docstring, or as a docstring on the __init__ method itself.

        Either form is acceptable, but the two should not be mixed. Choose one
        convention to document the __init__ method and be consistent with it.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            param1 (str): Description of `param1`.
            param2 (:obj:`int`, optional): Description of `param2`. Multiple
                lines are supported.
            param3 (:obj:`list` of :obj:`str`): Description of `param3`.

        """
        self.attr1 = param1
        self.attr2 = param2
```

```
**【错误示例】**

```
### 场景1：类的文档字符串格式
- 错误示例：类的文档字符串缩进不一致
```python
class Six:  # error
    """
功能描述：
接口：
"""

```
**【修复建议】**

类的文档字符串应位于类定义头部的下一行，相对于class关键字缩进4个空格，与内部定义的方法、数据成员具有相同的缩进量。

1.使用单行文档字符串时，前导三引号和结束三引号保持在同一行。

2.使用多行文档字符串时，以前导三引号开头，结束三引号要自成一行。
