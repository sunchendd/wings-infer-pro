# G.ERR.09 在单个except代码块内，禁止重复捕获同类异常

- **规则ID**：35f9d2e8-2919-491a-b939-0775c68c4ae8
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

在异常捕获语句中，重复捕获同类异常不会直接产生运行问题，但这不是好的编码习惯，在较长的软件生命周期中，会带来可读性和可维护性问题。

**【正确示例】**

```
### 场景1：同时捕获多个异常
- 修复示例：捕获异常属于不同异常类型
```python
try:
    with open(file_name) as fd:
        ...
except (FileNotFoundError, PermissionError):    # 符合
    ...
```

```
**【错误示例】**

```
### 场景1：同时捕获多个异常
- 错误示例：同时捕获父子异常类型
```python
try:
    with open(file_name) as fd:
        ...
except (FileNotFoundError, OSError):  # 不符合，FileNotFoundError继承自OSError，逻辑冗余
    ...
```

```
**【修复建议】**

捕获异常不要同时捕获父类异常和子类异常，不要重复捕获同一个异常。
