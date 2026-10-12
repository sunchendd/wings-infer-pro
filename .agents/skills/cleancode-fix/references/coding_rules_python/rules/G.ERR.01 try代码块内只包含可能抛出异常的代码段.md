# G.ERR.01 try代码块内只包含可能抛出异常的代码段

- **规则ID**：be46d80e-ea35-409b-8024-7b0336081b4d
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

如果在`try`代码块中包含了过多的代码，在`except`代码块内很难对各种异常做出合适的处理逻辑，从而导致代码臃肿，难以维护。

**【正确示例】**

```
### 场景1：try块逻辑的处理
- 修复示例：将读取文件与处理文件内容的异常处理分开，各代码段的职责独立且清晰。
```python
try:
    #  符合
    with open(file_name) as fd:
        content = fd.read()
except FileNotFoundError as e:
    do_something(file_name, e)
except UnicodeDecodeError as e:
    do_otherthing(file_name, e)

try:
    #  符合
    handle_file_content(content)
except UserDefined.FileFormatError as e:
    do_something(e)
```

```
**【错误示例】**

```
### 场景1：try块逻辑的处理
- 错误示例：放在`try`代码块中的代码段未保证逻辑的相对独立性。
```python
try:
    a = 1  # 不符合，不会产生异常的语句，应该放到try前面
    b = get_input()  # 不符合，get_input和a / b属于不同的语义逻辑且会引发不同异常
    result = a / b
except UserDefined.InputInvalid as e:
    do_something(e)
except ZeroDivisionError as e:
    do_otherthing(e)
```

```
**【修复建议】**

1. 只将可能引发异常的最小代码段放入`try`代码块内。

2. 一个`try`代码块只处理一段可能引发异常的代码。
