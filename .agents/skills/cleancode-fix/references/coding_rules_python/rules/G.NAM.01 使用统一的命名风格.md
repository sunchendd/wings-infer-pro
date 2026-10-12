# G.NAM.01 使用统一的命名风格

- **规则ID**：b0f1cdb9-9e77-4e6b-aab5-799d5992fa63
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

在标识符命名时，应使用统一的命名风格，如果标识符命名不规范，会出现代码可读性问题。

**【正确示例】**

```
##### 场景1：包和模块的命名风格
- 修复示例：包（Package）、模块（Module）名使用意义完整的英文描述，采用小写加下划线的风格命名
```python
from example_package import example_module  # 符合
from example_module import MyClass  # 符合
```
##### 场景2：类的命名风格
- 修复示例：类（Class）名使用意义完整的英文描述，采用大写字母开头的单词（CapWords）风格命名
```python
class MyClass:  # 符合
    def __init__(self):
    ....
```
##### 场景3：函数的命名风格
- 修复示例：函数、方法使用意义完整的英文描述，采用小写加下划线（lower_with_under）的风格命名
```python
def my_method():  # 符合
    ....
```
##### 场景4：类或对象的保护成员、私有成员的命名风格
- 修复示例：类或对象的保护成员一般用单下划线`_`开头，私有成员一般用双下划线`__`开头
```python
class MyClass:
    def __init__(self):
        self._member = 1  # 符合，单下划线开头，暗示此成员仅供类的内部操作使用，外部不应该访问

    def my_method(self):
        self._member += 1

    def _my_protected_method(self):  # 符合，单下划线开头，暗示此方法仅供类的内部操作使用，外部不应该访问
        pass


class Mapping:
    def __init__(self, iterable):
        self.items_list = []
        self.__update(iterable)

    # 双下划线开头，会被解释器改名为_Mapping__update，外部如果使用修改后的名字仍可访问
    def __update(self, iterable):
        for item in iterable:
            self.items_list.append(item)


class MappingSubclass(Mapping):
    # 双下划线开头，会被解释器改名为_MappingSubclass__update，不会跟基类成员重名
    def __update(self, keys, values):
        for item in zip(keys, values):
            self.items_list.append(item)
```
##### 场景5：变量（Variable）、类的数据成员（Data Member）、函数的参数(Parameter)的命名风格
- 修复示例：变量（Variable）、类的数据成员（Data Member）、函数的参数(Parameter)采用小写加下划线 （lower_with_under）的风格命名
```python
class FileEntry:
    def __init__(fd, buffer_size, buffer_offset):  # 符合
        self.file_descriptor = fd  # 符合
        self.buffer_size = buffer_size  # 符合
        self.buffer_offset = buffer_offset  # 符合
```
##### 场景6：常量（Constant）命名风格
- 修复示例：常量（Constant） 采用大写加下划线（CAPS_WITH_UNDER）的风格命名
```python
import enum


class State(enum.Enum):
    '''The internal state used for parsing the input file.'''
    NORMAL = 0  # 符合
    IGNORE = 1  # 符合
```

```
**【错误示例】**

```
##### 场景1：包和模块的命名风格
- 错误示例：
```python
from EXAMPLE_PACKAGE import example_module  # 不符合
from examplemodule import MyClass  # 不符合
```
##### 场景2：类的命名风格
- 错误示例：
```python
class myclass:  # 不符合
    def __init__(self):
 ....
```
##### 场景3：函数的命名风格
- 错误示例：
```python
def myMethod():  # 不符合
 ....
```
##### 场景4：类或对象的保护成员、私有成员的命名风格
- 错误示例：
```python
class Example:
    def __init__(self):
        self._bad_public_name = 10  # 不符合，公开属性变保护属性
        self.__bad_protect_name = 10  # 不符合，保护属性变私有属性
        self.bad_private_name = 11  # 不符合，私有属性变公开
        self.protect_name = 12  # 不符合，保护属性变公开

    def __public_method(self):  # 不符合，公开方法设置成私有，难以或者无法正常调用
        pass

    def private_method(self):  # 不符合，私有方法公开
        pass
```
##### 场景5：变量（Variable）、类的数据成员（Data Member）、函数的参数(Parameter)的命名风格
- 错误示例：
```python
class FileEntry:
    def __init__(fd, buffersize, bufferoffset):  # 不符合
        self.filedescriptor = fd  # 不符合
        self.buffersize = buffersize  # 不符合
        self.bufferoffset = bufferoffset  # 不符合
```
##### 场景6：常量（Constant）命名风格
- 错误示例：
```python
import enum


class State(enum.Enum):
    '''The internal state used for parsing the input file.'''
    normal = 0  # 不符合
    ignore = 1  # 不符合
```

```
**【修复建议】**

1. 常用标识符类型的命名风格推荐表：

| 类别  | 公有  |  私有 |

| ------------ | ------------ | ------------ |

|Modules |lower_with_under |_lower_with_under|

|Packages|lower_with_under   |   |

|Classes   |  CapWords |   |

| Exceptions  |   CapWords|   |

|Functions  |lower_with_under() | _lower_with_under() |

|Global/Class Constants  |  CAPS_WITH_UNDER |  _CAPS_WITH_UNDER  |

| Global/Class Variables   |  lower_with_under |  _lower_with_under |

|Instance Variables   |lower_with_under |_lower_with_under or __lower_with_under (当需要名字修饰时）  |

|Method Names   |  lower_with_under()|  _lower_with_under() or __lower_with_under() (当需要名字修饰时)|

|Function/Method Parameters   |  lower_with_under  |     |

|Local Variables|lower_with_under|  |

2. 如果项目不遵循本条款规范命名风格，此规则不适用，建议取消该规则的检查。

   - 基于开源或外部代码进行开发或维护时，可以保持原有命名风格，

   - 本条款未明确要求的标识符命名风格，由项目组自行选择，并保持风格统一。
