# G.NAM.04 避免在无关的标识符或无关的概念之间重用名字， 避免因重名而导致的意外赋值和错误引用

- **规则ID**：df3c5023-d840-4a4f-b0ab-607d4f7f9a07
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

重复定义一个函数/类的名字很容易掩盖编码问题，让同 一个名字的函数/类在不同的执行阶段具有不同的含义，不利于可读性，应予以禁止。

在代码修改时，同名的变量容易导致错误的引用，也不利于代码可读性，应当尽量避免。

**【正确示例】**

```
##### 场景1：参数和内建函数重名
- 修复示例：修改参数名避免和内建函数重名
```python
def function(para, typename):    # 符合
    ...
    para_type = type(para) 
```
##### 场景2：变量和导入对象重名
- 修复示例：修改变量名避免和导入对象重名
```python
from os import path

for file_name in ['file1.py', 'file2.py']:     # 符合
    print(file_name)
```
##### 场景3：变量名和函数参数名重名
- 修复示例：修改变量名避免和函数参数重名
```python
from os import path


def redefine_argument(file_name):     
    with open('file.py') as some_file:      # 符合
        pass
```


```
**【错误示例】**

```
##### 场景1：参数和内建函数重名
- 错误示例：参数名遮盖了builtin函数type
```python
def function(para, type):  
    ...
    para_type = type(para)  # 不符合，type被遮盖为函数参数，不是builtin的实现
```
##### 场景2：变量和导入对象重名
- 错误示例：循环变量path与导入的对象path重名
```python
from os import path

for path in ['file1.py', 'file2.py']:    # 不符合，path变量和导入模块名重名
    print(path)
```
##### 场景3：变量名和函数参数名重名
- 错误示例：file_name变量与函数参数名称重名，可能导致潜在的错误
```python
def not_redefine_argument(file_name):    
    with open('file.py') as file_name:          # 不符合，file_name变量名和参数名称重名
        pass
```


```
**【修复建议】**

应避免重用名字的场景如下：

  1. 标识符的命名避免和内置函数、内置类以及Python关键字重复。

  2. 避免重复定义函数、类方法或类。

  3. 标识符命名避免与当前导入的模块名称重名。

  4. 避免在函数中定义与参数名称相同的变量，这可能导致潜在的错误。
