# G.VAR.03 禁止覆盖外部作用域中的标识符

- **规则ID**：0625832e-355e-48fc-82dc-ed3972c218c1
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

禁止出现当前局部作用域遮盖更外层作用域中的标识符，给阅读者带来困扰，无法清晰知道在使用哪个变量。

**【正确示例】**

```
### 场景1：局部变量和全局变量重名
- 修复示例：修改局部变量名称避免和外部变量重名
```python
_global = 1


def test():
    local_number = 2  # 符合
    if local_number == _global:
        raise MyException
```
### 场景2：全局变量和函数参数重名
- 修复示例：修改外部变量名称避免和函数参数重名
```python
AGE= None


def test(age): # 符合
    local_number = 2  
```

- 修复示例：修改函数参数名称避免和外部变量重名
```python
age= None


def test(age_val): # 符合
    local_number = 2  
```
### 场景3：导入对象和内部变量重名
- 修复示例：修改内部变量避免和外部导入对象重名
```python
from os import path

def test():
    temp_path = '/usr/bin/python3' # 符合
    os.path.join(temp_path, "lib/sitepackages")
    print(temp_path)
```

- 修复示例：修改外部导入方式避免和内部变量重名
```python
import os


def test():
    path = '/usr/bin/python3' # 符合
    os.path.join(path, "lib/sitepackages")
    print(path)
```

```
**【错误示例】**

```
### 场景1：局部变量和全局变量重名
- 错误示例：函数内部变量和外部的变量重名
```python
_global = 1


def test():
    _global = 2  # 不符合, 更外层作用域（模块命名空间）中变量被遮盖
    ...
```
### 场景2：全局变量和函数参数重名
- 错误示例：函数内部变量和外部的变量重名
```python
age = None


def test(age ): # 不符合, 函数参数和全局变量重名
    ...
```
### 场景3：导入对象和内部变量重名
- 错误示例：函数内部变量和外部导入模块重名
```python
from os import path


def test():
    path = '/usr/bin/python' # 不符合, 局部变量和外部导入对象重名
    print(path)
    ...
```

```
**【修复建议】**

避免局部变量和全局变量重名，以及参数，导入对象和本模块内部对象重名等。
