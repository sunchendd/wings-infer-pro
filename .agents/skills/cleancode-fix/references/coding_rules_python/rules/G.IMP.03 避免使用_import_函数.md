# G.IMP.03 避免使用__import__函数

- **规则ID**：f5ba88cb-3292-46fd-8707-2136610769b2
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

建议使用`importlib.import_module`函数替代`__builtins.__import__`。

在`importlib`模块中，提供了比内置函数`__import__`更为丰富的接口，不需要关注导入细节，使用更为简单。

**【正确示例】**

```
##### 场景1：动态导入模块
- 修复示例：使用importlib动态导入模块
```python
import importlib


# 以下用法为建议用法
os_path_recommend = importlib.import_module('os.path')
# <module 'posixpath' from '.../pythonX/posixpath.py'>

```

```
**【错误示例】**

```
##### 场景1：动态导入模块
- 错误示例：使用__import__动态导入模块
```python
os_path_negative = __import__('os.path')
# <module 'os' from '.../pythonX/os.py'>
```

```
**【修复建议】**

使用`importlib.import_module`函数来动态导入模块。
